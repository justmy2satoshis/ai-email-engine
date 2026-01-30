"""Email processor — orchestrates classification and link extraction for synced emails."""

import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.email import Email
from app.models.classification import EmailClassification
from app.models.link import ExtractedLink
from app.models.sender import SenderProfile
from app.services.classifier import email_classifier, ClassificationResult
from app.services.email_parser import extract_links

logger = logging.getLogger(__name__)


class EmailProcessor:
    """Processes emails: classifies, extracts links, updates sender profiles."""

    async def process_unclassified(self, limit: int = 50) -> dict:
        """Find and process emails that haven't been classified yet."""
        result = {"processed": 0, "errors": 0, "links_found": 0}

        async with async_session() as db:
            # Find emails without classifications
            subquery = select(EmailClassification.email_id)
            query = (
                select(Email)
                .where(~Email.id.in_(subquery))
                .order_by(Email.date_sent.desc())
                .limit(limit)
            )
            emails_result = await db.execute(query)
            emails = emails_result.scalars().all()

            if not emails:
                logger.info("No unclassified emails found")
                return result

            logger.info(f"Processing {len(emails)} unclassified emails...")

            for email_obj in emails:
                try:
                    await self._process_single(db, email_obj)
                    result["processed"] += 1
                except Exception as e:
                    logger.error(f"Failed to process email {email_obj.id}: {e}")
                    result["errors"] += 1

        return result

    async def process_email_by_id(self, email_id: int) -> Optional[dict]:
        """Process a specific email by ID."""
        async with async_session() as db:
            email_obj = await db.get(Email, email_id)
            if not email_obj:
                return None

            return await self._process_single(db, email_obj)

    async def _process_single(self, db: AsyncSession, email_obj: Email) -> dict:
        """Process a single email: classify + extract links + update sender."""
        result = {"email_id": email_obj.id, "links_found": 0}

        # Step 1: Classify with AI
        date_str = email_obj.date_sent.isoformat() if email_obj.date_sent else None
        classification = await email_classifier.classify_email(
            subject=email_obj.subject,
            from_name=email_obj.from_name,
            from_address=email_obj.from_address,
            body_text=email_obj.body_text,
            date_sent=date_str,
        )

        # Store classification
        db_classification = EmailClassification(
            email_id=email_obj.id,
            category=classification.category,
            confidence=classification.confidence,
            topics=classification.topics,
            relevance_score=classification.relevance_score,
            summary=classification.summary,
            model_used=classification.model_used,
        )
        db.add(db_classification)
        result["category"] = classification.category
        result["relevance"] = classification.relevance_score
        result["summary"] = classification.summary

        # Step 2: Extract and score links
        links = extract_links(email_obj.body_html, email_obj.body_text)
        if links:
            # Score links with AI
            scored_links = await email_classifier.score_links(
                links=links,
                subject=email_obj.subject,
                from_address=email_obj.from_address,
                category=classification.category,
            )

            for scored in scored_links:
                domain = _extract_domain(scored.url)
                db_link = ExtractedLink(
                    email_id=email_obj.id,
                    url=scored.url,
                    domain=domain,
                    link_type=scored.link_type,
                    relevance_score=scored.relevance_score,
                    pipeline_status="pending" if scored.relevance_score >= 0.5 else "skipped",
                )
                db.add(db_link)
                result["links_found"] += 1

        # Step 3: Update sender profile
        if email_obj.from_address:
            await self._update_sender_profile(db, email_obj, classification)

        await db.commit()

        logger.info(
            f"Processed email {email_obj.id}: "
            f"category={classification.category}, "
            f"relevance={classification.relevance_score:.2f}, "
            f"links={result['links_found']}"
        )
        return result

    async def _update_sender_profile(
        self, db: AsyncSession, email_obj: Email, classification: ClassificationResult
    ):
        """Update or create sender profile based on classification."""
        result = await db.execute(
            select(SenderProfile).where(
                SenderProfile.email_address == email_obj.from_address
            )
        )
        profile = result.scalar_one_or_none()

        if profile is None:
            profile = SenderProfile(
                email_address=email_obj.from_address,
                display_name=email_obj.from_name,
                sender_type=self._infer_sender_type(classification.category),
                total_emails=1,
                emails_opened=1 if email_obj.is_read else 0,
                first_seen=email_obj.date_sent or datetime.now(timezone.utc),
                last_seen=email_obj.date_sent or datetime.now(timezone.utc),
                relevance_score=classification.relevance_score,
            )
            db.add(profile)
        else:
            profile.total_emails += 1
            if email_obj.is_read:
                profile.emails_opened += 1
            if email_obj.date_sent and (profile.last_seen is None or email_obj.date_sent > profile.last_seen):
                profile.last_seen = email_obj.date_sent
            # Rolling average of relevance
            if profile.relevance_score is not None:
                profile.relevance_score = (
                    profile.relevance_score * 0.8 + classification.relevance_score * 0.2
                )
            else:
                profile.relevance_score = classification.relevance_score
            profile.updated_at = datetime.now(timezone.utc)

    @staticmethod
    def _infer_sender_type(category: str) -> str:
        """Infer sender type from email category."""
        mapping = {
            "newsletter": "newsletter",
            "transactional": "service",
            "notification": "service",
            "personal": "person",
            "marketing": "marketing",
            "actionable": "person",
            "noise": "marketing",
        }
        return mapping.get(category, "service")

    async def get_processing_stats(self) -> dict:
        """Get current processing statistics."""
        async with async_session() as db:
            total_emails = (await db.execute(select(func.count(Email.id)))).scalar() or 0
            classified = (await db.execute(
                select(func.count(EmailClassification.id))
            )).scalar() or 0
            total_links = (await db.execute(
                select(func.count(ExtractedLink.id))
            )).scalar() or 0
            pending_links = (await db.execute(
                select(func.count(ExtractedLink.id)).where(
                    ExtractedLink.pipeline_status == "pending"
                )
            )).scalar() or 0
            total_senders = (await db.execute(
                select(func.count(SenderProfile.id))
            )).scalar() or 0

            # Category breakdown
            cat_query = select(
                EmailClassification.category,
                func.count(EmailClassification.id),
            ).group_by(EmailClassification.category)
            cat_result = await db.execute(cat_query)
            by_category = {row[0]: row[1] for row in cat_result.all()}

            return {
                "total_emails": total_emails,
                "classified": classified,
                "unclassified": total_emails - classified,
                "total_links": total_links,
                "pending_links": pending_links,
                "total_senders": total_senders,
                "by_category": by_category,
            }


def _extract_domain(url: str) -> Optional[str]:
    """Extract domain from a URL."""
    try:
        parsed = urlparse(url)
        return parsed.netloc or None
    except Exception:
        return None


# Singleton
email_processor = EmailProcessor()
