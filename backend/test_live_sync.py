"""Live sync test — connect to Bridge, list folders, sync a small batch."""

import asyncio
import sys
sys.path.insert(0, ".")


async def test():
    print("=" * 60)
    print("AI Email Engine — Live IMAP Sync Test")
    print("=" * 60)

    from app.config import settings
    from app.database import init_db, engine
    from app.services.imap_sync import imap_sync

    # Init DB
    await init_db()
    print("[OK] Database ready")

    # Connect
    print(f"\nConnecting to {settings.imap_host}:{settings.imap_port}...")
    connected = await imap_sync.connect()
    if not connected:
        print(f"[FAIL] Connection failed: {imap_sync.last_error}")
        await engine.dispose()
        return

    print("[OK] Connected to Proton Mail Bridge!")

    # List folders
    print("\nListing folders...")
    folders = await imap_sync.list_folders()
    if folders:
        print(f"[OK] Found {len(folders)} folders:")
        for f in folders:
            print(f"  - {f}")
    else:
        print("[WARN] No folders returned (may be a parsing issue)")
        print("  Trying INBOX directly...")

    # Get INBOX count
    print("\nChecking INBOX...")
    count = await imap_sync.get_folder_count("INBOX")
    print(f"[OK] INBOX has {count} messages")

    # Sync a small batch
    print(f"\nSyncing first 10 emails...")
    result = await imap_sync.sync_folder(folder="INBOX", limit=10)
    print(f"[OK] Sync result:")
    for k, v in result.items():
        print(f"  {k}: {v}")

    # Check what we got
    from sqlalchemy import select, func
    from app.database import async_session
    from app.models.email import Email

    async with async_session() as db:
        total = (await db.execute(select(func.count(Email.id)))).scalar() or 0
        print(f"\n[OK] Total emails in DB: {total}")

        if total > 0:
            # Show first few
            result = await db.execute(
                select(Email).order_by(Email.date_sent.desc()).limit(5)
            )
            emails = result.scalars().all()
            print("\nLatest emails:")
            for e in emails:
                date = e.date_sent.strftime("%Y-%m-%d %H:%M") if e.date_sent else "unknown"
                print(f"  [{date}] {e.from_address}: {e.subject[:60] if e.subject else '(no subject)'}")

    # Disconnect
    await imap_sync.disconnect()
    await engine.dispose()

    print("\n" + "=" * 60)
    print("[OK] Live sync test complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test())
