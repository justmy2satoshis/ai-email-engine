"""IMAP sync service — connects to Proton Mail Bridge and syncs emails."""

import asyncio
import logging
import ssl
from datetime import datetime, timezone
from typing import Optional

import aioimaplib
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.database import async_session
from app.models.email import Email
from app.models.sync_state import SyncState
from app.services.email_parser import parse_raw_email, ParsedEmail

logger = logging.getLogger(__name__)


class IMAPSyncService:
    """Handles IMAP connection and email synchronization."""

    def __init__(self):
        self._client: Optional[aioimaplib.IMAP4_SSL] = None
        self._connected = False
        self._syncing = False
        self._last_error: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_syncing(self) -> bool:
        return self._syncing

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    async def connect(self) -> bool:
        """Establish IMAP connection to Proton Mail Bridge."""
        try:
            logger.info(f"Connecting to IMAP: {settings.imap_host}:{settings.imap_port}")

            if settings.imap_use_ssl:
                # Proton Bridge uses a self-signed cert — we need to accept it
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                self._client = aioimaplib.IMAP4_SSL(
                    host=settings.imap_host,
                    port=settings.imap_port,
                    ssl_context=ssl_context,
                    timeout=30,
                )
            else:
                self._client = aioimaplib.IMAP4(
                    host=settings.imap_host,
                    port=settings.imap_port,
                    timeout=30,
                )

            await self._client.wait_hello_from_server()

            # Login
            response = await self._client.login(settings.imap_user, settings.imap_password)
            if response.result != "OK":
                self._last_error = f"Login failed: {response.lines}"
                logger.error(self._last_error)
                return False

            self._connected = True
            self._last_error = None
            logger.info("IMAP connection established successfully")
            return True

        except Exception as e:
            self._last_error = f"Connection failed: {str(e)}"
            logger.error(self._last_error)
            self._connected = False
            return False

    async def disconnect(self):
        """Close the IMAP connection."""
        if self._client:
            try:
                await self._client.logout()
            except Exception:
                pass
            self._client = None
        self._connected = False

    async def list_folders(self) -> list[str]:
        """List available IMAP folders."""
        if not self._connected:
            return []

        try:
            response = await self._client.list()
            if response.result != "OK":
                return []

            folders = []
            for line in response.lines:
                line_str = line if isinstance(line, str) else line.decode("utf-8", errors="replace")
                if line_str:
                    # Parse IMAP LIST response: (\Flags) "delimiter" "folder_name"
                    parts = line_str.rsplit('"', 2)
                    if len(parts) >= 2:
                        folder_name = parts[-1].strip().strip('"')
                        if folder_name:
                            folders.append(folder_name)
            return folders
        except Exception as e:
            logger.error(f"Failed to list folders: {e}")
            return []

    async def get_folder_count(self, folder: str = "INBOX") -> int:
        """Get the number of messages in a folder."""
        if not self._connected:
            return 0

        try:
            response = await self._client.select(folder)
            if response.result != "OK":
                return 0
            # The EXISTS count is in the response data
            for line in response.lines:
                line_str = line if isinstance(line, str) else line.decode("utf-8", errors="replace")
                if "EXISTS" in str(line_str):
                    count = int(str(line_str).split()[0])
                    return count
            return 0
        except Exception as e:
            logger.error(f"Failed to get folder count for {folder}: {e}")
            return 0

    async def sync_folder(self, folder: str = "INBOX", limit: Optional[int] = None) -> dict:
        """
        Sync a folder incrementally — only fetch emails newer than last sync.

        Returns a dict with sync results: new_emails, errors, total_in_folder.
        """
        if not self._connected:
            return {"error": "Not connected", "new_emails": 0}

        if self._syncing:
            return {"error": "Sync already in progress", "new_emails": 0}

        self._syncing = True
        result = {"folder": folder, "new_emails": 0, "errors": 0, "skipped": 0}

        try:
            # Select folder
            select_response = await self._client.select(folder)
            if select_response.result != "OK":
                result["error"] = f"Failed to select folder: {folder}"
                return result

            # Get sync state from DB
            async with async_session() as db:
                sync_state = await self._get_or_create_sync_state(db, folder)
                last_uid = sync_state.last_uid

            # Search for messages with UID greater than last synced
            if last_uid > 0:
                search_criteria = f"UID {last_uid + 1}:*"
            else:
                search_criteria = "ALL"

            search_response = await self._client.uid_search(search_criteria)
            if search_response.result != "OK":
                result["error"] = f"Search failed: {search_response.lines}"
                return result

            # Parse UIDs from search response
            uid_line = search_response.lines[0] if search_response.lines else ""
            uid_str = uid_line if isinstance(uid_line, str) else uid_line.decode("utf-8", errors="replace")
            uids = [int(u) for u in uid_str.split() if u.strip().isdigit()]

            # Filter out UIDs we already have
            uids = [u for u in uids if u > last_uid]

            if not uids:
                logger.info(f"No new emails in {folder} (last UID: {last_uid})")
                result["message"] = "Up to date"
                return result

            # Apply limit
            if limit and len(uids) > limit:
                uids = uids[:limit]
                logger.info(f"Limited to {limit} of {len(uids)} new emails")

            logger.info(f"Syncing {len(uids)} new emails from {folder} (UIDs {uids[0]}-{uids[-1]})")

            # Fetch and store emails
            max_uid = last_uid
            for uid in uids:
                try:
                    parsed = await self._fetch_email(uid, folder)
                    if parsed:
                        async with async_session() as db:
                            stored = await self._store_email(db, parsed, uid, folder)
                            if stored:
                                result["new_emails"] += 1
                            else:
                                result["skipped"] += 1
                        max_uid = max(max_uid, uid)
                except Exception as e:
                    logger.error(f"Failed to process UID {uid}: {e}")
                    result["errors"] += 1

            # Update sync state
            if max_uid > last_uid:
                async with async_session() as db:
                    await self._update_sync_state(db, folder, max_uid, result["new_emails"])

            logger.info(
                f"Sync complete: {result['new_emails']} new, "
                f"{result['skipped']} skipped, {result['errors']} errors"
            )
            return result

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Sync failed: {e}")
            return result
        finally:
            self._syncing = False

    async def _fetch_email(self, uid: int, folder: str) -> Optional[ParsedEmail]:
        """Fetch a single email by UID."""
        try:
            # Fetch message data and flags
            response = await self._client.uid(
                "fetch", str(uid), "(FLAGS RFC822)"
            )
            if response.result != "OK":
                logger.warning(f"Failed to fetch UID {uid}: {response.lines}")
                return None

            # Parse response — aioimaplib returns data in response.lines
            raw_data = None
            flags = ()

            for item in response.lines:
                if isinstance(item, bytes):
                    raw_data = item
                elif isinstance(item, str) and "FLAGS" in item:
                    # Extract flags from the response
                    import re
                    flags_match = re.search(r'FLAGS \(([^)]*)\)', item)
                    if flags_match:
                        flags = tuple(f.encode() for f in flags_match.group(1).split())

            if raw_data is None:
                logger.warning(f"No message data for UID {uid}")
                return None

            return parse_raw_email(raw_data, uid=uid, folder=folder, flags=flags)

        except Exception as e:
            logger.error(f"Error fetching UID {uid}: {e}")
            return None

    async def _store_email(self, db: AsyncSession, parsed: ParsedEmail, uid: int, folder: str) -> bool:
        """Store a parsed email in the database. Returns True if new, False if duplicate."""
        try:
            # Use upsert to handle duplicates gracefully
            stmt = pg_insert(Email).values(
                message_id=parsed.message_id,
                uid=uid,
                folder=folder,
                from_address=parsed.from_address,
                from_name=parsed.from_name,
                to_addresses=parsed.to_addresses,
                cc_addresses=parsed.cc_addresses,
                reply_to=parsed.reply_to,
                subject=parsed.subject,
                body_text=parsed.body_text,
                body_html=parsed.body_html,
                date_sent=parsed.date_sent,
                date_synced=datetime.now(timezone.utc),
                is_read=parsed.is_read,
                has_attachments=parsed.has_attachments,
                size_bytes=parsed.size_bytes,
                raw_headers=parsed.raw_headers,
            ).on_conflict_do_nothing(index_elements=["message_id"])

            result = await db.execute(stmt)
            await db.commit()

            # result.rowcount > 0 means it was inserted (not a duplicate)
            return result.rowcount > 0

        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to store email {parsed.message_id}: {e}")
            return False

    async def _get_or_create_sync_state(self, db: AsyncSession, folder: str) -> SyncState:
        """Get or create sync state for a folder."""
        result = await db.execute(
            select(SyncState).where(SyncState.folder == folder)
        )
        state = result.scalar_one_or_none()

        if state is None:
            state = SyncState(folder=folder, last_uid=0, total_synced=0)
            db.add(state)
            await db.commit()
            await db.refresh(state)

        return state

    async def _update_sync_state(self, db: AsyncSession, folder: str, last_uid: int, new_count: int):
        """Update sync state after successful sync."""
        result = await db.execute(
            select(SyncState).where(SyncState.folder == folder)
        )
        state = result.scalar_one_or_none()

        if state:
            state.last_uid = last_uid
            state.last_sync = datetime.now(timezone.utc)
            state.total_synced += new_count
            await db.commit()


# Singleton instance
imap_sync = IMAPSyncService()
