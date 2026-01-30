"""Test email classification with Ollama — processes real synced emails."""

import asyncio
import sys
sys.path.insert(0, ".")


async def test():
    print("=" * 60)
    print("AI Email Engine — Classification Test")
    print("=" * 60)

    from app.database import init_db, engine, async_session
    from app.services.processor import email_processor
    from app.models.email import Email
    from app.models.classification import EmailClassification
    from app.models.link import ExtractedLink
    from app.models.sender import SenderProfile
    from sqlalchemy import select, func

    await init_db()

    # Check what we have
    async with async_session() as db:
        total = (await db.execute(select(func.count(Email.id)))).scalar() or 0
        classified = (await db.execute(select(func.count(EmailClassification.id)))).scalar() or 0
        print(f"\nEmails in DB: {total}")
        print(f"Already classified: {classified}")
        print(f"Unclassified: {total - classified}")

    if total == 0:
        print("\nNo emails to classify. Run test_live_sync.py first.")
        await engine.dispose()
        return

    # Process a small batch
    batch_size = min(5, total - classified)
    if batch_size <= 0:
        print("\nAll emails already classified!")
    else:
        print(f"\nClassifying {batch_size} emails with Ollama...")
        print("(This may take a minute — each email gets AI analysis)\n")

        result = await email_processor.process_unclassified(limit=batch_size)
        print(f"Processed: {result['processed']}")
        print(f"Errors: {result['errors']}")
        print(f"Links found: {result.get('links_found', 0)}")

    # Show results
    async with async_session() as db:
        # Classifications
        cls_result = await db.execute(
            select(EmailClassification, Email)
            .join(Email)
            .order_by(EmailClassification.relevance_score.desc())
            .limit(10)
        )
        rows = cls_result.all()

        if rows:
            print("\n--- Classification Results ---")
            for cls, email in rows:
                print(f"\n  [{cls.category}] (rel={cls.relevance_score:.2f}, conf={cls.confidence:.2f})")
                print(f"  From: {email.from_address}")
                print(f"  Subject: {email.subject[:70] if email.subject else '(none)'}")
                print(f"  Topics: {', '.join(cls.topics) if cls.topics else 'none'}")
                print(f"  Summary: {cls.summary[:100] if cls.summary else 'none'}")

        # Links
        link_result = await db.execute(
            select(ExtractedLink)
            .order_by(ExtractedLink.relevance_score.desc())
            .limit(10)
        )
        links = link_result.scalars().all()

        if links:
            print("\n--- Extracted Links (top by relevance) ---")
            for link in links:
                status_icon = "[QUEUE]" if link.pipeline_status == "pending" else "[skip]"
                print(f"  {status_icon} ({link.relevance_score:.2f}) [{link.link_type}] {link.url[:80]}")

        # Senders
        sender_result = await db.execute(
            select(SenderProfile)
            .order_by(SenderProfile.total_emails.desc())
            .limit(5)
        )
        senders = sender_result.scalars().all()

        if senders:
            print("\n--- Sender Profiles ---")
            for s in senders:
                print(f"  {s.email_address} ({s.sender_type}): {s.total_emails} emails, rel={s.relevance_score:.2f}")

    # Stats
    stats = await email_processor.get_processing_stats()
    print("\n--- Processing Stats ---")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    await engine.dispose()
    print("\n" + "=" * 60)
    print("Classification test complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test())
