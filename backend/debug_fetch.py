"""Debug — inspect what aioimaplib actually returns from FETCH."""

import asyncio
import ssl
import sys
sys.path.insert(0, ".")


async def test():
    import aioimaplib
    from app.config import settings

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    client = aioimaplib.IMAP4_SSL(
        host=settings.imap_host,
        port=settings.imap_port,
        ssl_context=ssl_context,
        timeout=30,
    )
    await client.wait_hello_from_server()
    await client.login(settings.imap_user, settings.imap_password)
    await client.select("INBOX")

    # Search for the most recent UID
    resp = await client.uid_search("ALL")
    uid_str = resp.lines[0] if resp.lines else ""
    if isinstance(uid_str, bytes):
        uid_str = uid_str.decode()
    uids = uid_str.split()
    
    if not uids:
        print("No UIDs found")
        return

    # Get last UID
    last_uid = uids[-1]
    print(f"Fetching UID {last_uid}...")
    print()

    # Fetch it
    response = await client.uid("fetch", last_uid, "(FLAGS RFC822)")
    print(f"Result: {response.result}")
    print(f"Lines count: {len(response.lines)}")
    print()

    for i, item in enumerate(response.lines):
        item_type = type(item).__name__
        if isinstance(item, bytes):
            preview = item[:500].decode("utf-8", errors="replace")
            print(f"Line {i} [{item_type}, {len(item)} bytes]:")
            print(f"  {preview[:300]}...")
        elif isinstance(item, bytearray):
            preview = bytes(item)[:500].decode("utf-8", errors="replace")
            print(f"Line {i} [{item_type}, {len(item)} bytes]:")
            print(f"  {preview[:300]}...")
        else:
            print(f"Line {i} [{item_type}]: {str(item)[:300]}")
        print()

    await client.logout()


if __name__ == "__main__":
    asyncio.run(test())
