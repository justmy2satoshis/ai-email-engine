"""Sync control and status API endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.imap_sync import imap_sync
from app.database import async_session
from app.models.sync_state import SyncState
from app.models.email import Email
from sqlalchemy import select, func

router = APIRouter(prefix="/api/sync", tags=["sync"])


class SyncStatus(BaseModel):
    connected: bool
    syncing: bool
    last_error: Optional[str]
    folders: list[str] = []
    stats: dict = {}


class SyncResult(BaseModel):
    folder: str
    new_emails: int
    errors: int
    skipped: int
    message: Optional[str] = None
    error: Optional[str] = None


@router.get("/status", response_model=SyncStatus)
async def get_sync_status():
    """Get current IMAP connection and sync status."""
    status = SyncStatus(
        connected=imap_sync.is_connected,
        syncing=imap_sync.is_syncing,
        last_error=imap_sync.last_error,
    )

    # Get folder list if connected
    if imap_sync.is_connected:
        status.folders = await imap_sync.list_folders()

    # Get DB stats
    async with async_session() as db:
        # Total emails
        total = await db.execute(select(func.count(Email.id)))
        status.stats["total_emails"] = total.scalar() or 0

        # Sync states
        states = await db.execute(select(SyncState))
        status.stats["sync_states"] = [
            {
                "folder": s.folder,
                "last_uid": s.last_uid,
                "last_sync": s.last_sync.isoformat() if s.last_sync else None,
                "total_synced": s.total_synced,
            }
            for s in states.scalars().all()
        ]

    return status


@router.post("/connect")
async def connect_imap():
    """Connect to IMAP server (Proton Mail Bridge)."""
    if imap_sync.is_connected:
        return {"status": "already_connected"}

    success = await imap_sync.connect()
    if success:
        folders = await imap_sync.list_folders()
        return {"status": "connected", "folders": folders}
    else:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect: {imap_sync.last_error}",
        )


@router.post("/disconnect")
async def disconnect_imap():
    """Disconnect from IMAP server."""
    await imap_sync.disconnect()
    return {"status": "disconnected"}


@router.post("/run", response_model=SyncResult)
async def run_sync(folder: str = "INBOX", limit: Optional[int] = None):
    """Run a sync for the specified folder."""
    if not imap_sync.is_connected:
        # Try to connect first
        success = await imap_sync.connect()
        if not success:
            raise HTTPException(
                status_code=503,
                detail=f"Not connected and failed to connect: {imap_sync.last_error}",
            )

    result = await imap_sync.sync_folder(folder=folder, limit=limit)
    return SyncResult(**result)


@router.get("/folder/{folder}/count")
async def get_folder_count(folder: str):
    """Get the message count for an IMAP folder."""
    if not imap_sync.is_connected:
        raise HTTPException(status_code=503, detail="Not connected to IMAP")

    count = await imap_sync.get_folder_count(folder)
    return {"folder": folder, "count": count}
