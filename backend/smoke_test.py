"""Smoke test — verify imports, DB connection, and basic app setup."""

import asyncio
import sys
sys.path.insert(0, ".")

async def test():
    print("=" * 50)
    print("AI Email Engine — Smoke Test")
    print("=" * 50)

    # Test imports
    print("\n[1] Testing imports...")
    try:
        from app.config import settings
        from app.database import engine, init_db, Base
        from app.models import Email, EmailClassification, ExtractedLink, SenderProfile, CleanupProposal, SyncState
        from app.services.email_parser import parse_raw_email, ParsedEmail
        from app.services.imap_sync import imap_sync
        from app.main import app
        print("    ✅ All imports OK")
    except Exception as e:
        print(f"    ❌ Import error: {e}")
        return

    # Test config
    print("\n[2] Testing config...")
    print(f"    IMAP: {settings.imap_host}:{settings.imap_port}")
    print(f"    DB: {settings.database_url.split('@')[-1]}")
    print(f"    Ollama: {settings.ollama_url}")
    print(f"    Sync folders: {settings.sync_folder_list}")
    print("    ✅ Config OK")

    # Test DB connection
    print("\n[3] Testing database...")
    try:
        await init_db()
        print("    ✅ Database tables created")
    except Exception as e:
        print(f"    ❌ Database error: {e}")
        return

    # Test email parser
    print("\n[4] Testing email parser...")
    try:
        raw = b"""From: Test User <test@example.com>
To: me@example.com
Subject: Test Email with Links
Date: Thu, 30 Jan 2026 10:00:00 +0000
Message-ID: <test-123@example.com>
Content-Type: text/html; charset=utf-8

<html><body>
<p>Check out this article: <a href="https://arxiv.org/abs/2401.12345">Cool Paper</a></p>
<p>And this repo: <a href="https://github.com/cool/project">GitHub Link</a></p>
<p>Unsubscribe: <a href="https://unsubscribe.example.com/track/123">here</a></p>
</body></html>
"""
        parsed = parse_raw_email(raw, uid=1)
        print(f"    Subject: {parsed.subject}")
        print(f"    From: {parsed.from_name} <{parsed.from_address}>")
        print(f"    Links found: {len(parsed.links)}")
        for link in parsed.links:
            print(f"      → {link}")
        assert len(parsed.links) == 2, f"Expected 2 links (junk filtered), got {len(parsed.links)}"
        print("    ✅ Parser OK (junk URLs filtered correctly)")
    except Exception as e:
        print(f"    ❌ Parser error: {e}")
        return

    # Test IMAP connection (non-fatal — Bridge may not be running)
    print("\n[5] Testing IMAP connection...")
    if settings.imap_user:
        connected = await imap_sync.connect()
        if connected:
            folders = await imap_sync.list_folders()
            print(f"    ✅ Connected! Folders: {folders}")
            await imap_sync.disconnect()
        else:
            print(f"    ⚠️  Not connected: {imap_sync.last_error}")
            print("    (This is OK if Proton Mail Bridge isn't running)")
    else:
        print("    ⚠️  No IMAP_USER configured — skipping connection test")
        print("    Set IMAP_USER and IMAP_PASSWORD in .env to enable")

    # Test FastAPI app
    print("\n[6] Testing FastAPI app...")
    try:
        from fastapi.testclient import TestClient
        # Note: TestClient is sync, good for basic route testing
        print(f"    Routes: {len(app.routes)}")
        print("    ✅ App created OK")
    except Exception as e:
        print(f"    ❌ App error: {e}")

    print("\n" + "=" * 50)
    print("✅ SMOKE TEST PASSED — Phase 1 scaffolding complete")
    print("=" * 50)
    print("\nNext steps:")
    print("  1. Copy .env.example to .env and set IMAP credentials")
    print("  2. Start: uvicorn app.main:app --host 0.0.0.0 --port 8400 --reload")
    print("  3. Visit: http://localhost:8400/docs")
    print("  4. Connect: POST /api/sync/connect")
    print("  5. Sync: POST /api/sync/run")

    # Cleanup
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(test())
