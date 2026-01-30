"""Proposal engine — generates AI-driven inbox cleanup proposals."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.email import Email
from app.models.classification import EmailClassification
from app.models.link import ExtractedLink
from app.models.sender import SenderProfile
from app.models.proposal import CleanupProposal, ProposalItem

logger = logging.getLogger(__name__)


class ProposalEngine:
    """Generates inbox cleanup proposals based on sender intelligence and email analysis."""

    async def generate_all_proposals(self) -> list[dict]:
        """Run all proposal generators and return summaries."""
        results = []

        generators = [
            ("unsubscribe", self.generate_unsubscribe_proposals),
            ("archive", self.generate_archive_proposals),
            ("extraction", self.generate_extraction_proposals),
        ]

        for name, generator in generators:
            try:
                proposal = await generator()
                if proposal:
                    results.append(proposal)
                    logger.info(f"Generated {name} proposal: {proposal.get('title', 'untitled')}")
            except Exception as e:
                logger.error(f"Failed to generate {name} proposal: {e}")

        return results

    async def generate_unsubscribe_proposals(self) -> Optional[dict]:
        """Find senders with low engagement — propose unsubscribe."""
        async with async_session() as db:
            # Find newsletter/marketing senders with low relevance
            result = await db.execute(
                select(SenderProfile)
                .where(
                    and_(
                        SenderProfile.sender_type.in_(["newsletter", "marketing"]),
                        SenderProfile.total_emails >= 3,
                        or_(
                            SenderProfile.relevance_score < 0.3,
                            SenderProfile.relevance_score.is_(None),
                        ),
                    )
                )
                .order_by(SenderProfile.total_emails.desc())
            )
            low_engagement_senders = result.scalars().all()

            if not low_engagement_senders:
                return None

            # Calculate total affected emails
            total_affected = sum(s.total_emails for s in low_engagement_senders)

            # Create proposal
            proposal = CleanupProposal(
                proposal_type="unsubscribe",
                title=f"{len(low_engagement_senders)} low-value senders ({total_affected} emails)",
                description=(
                    f"Found {len(low_engagement_senders)} newsletter/marketing senders "
                    f"with low relevance scores (< 0.3). Together they sent {total_affected} emails. "
                    f"Consider unsubscribing to reduce inbox noise."
                ),
                affected_count=total_affected,
                affected_query={
                    "type": "low_relevance_senders",
                    "threshold": 0.3,
                    "sender_types": ["newsletter", "marketing"],
                },
                proposed_action={"action": "unsubscribe", "archive_existing": True},
                status="pending",
            )
            db.add(proposal)
            await db.flush()

            # Add items
            for sender in low_engagement_senders:
                item = ProposalItem(
                    proposal_id=proposal.id,
                    sender_id=sender.id,
                    action="unsubscribe",
                    reason=(
                        f"{sender.total_emails} emails, "
                        f"relevance: {sender.relevance_score:.2f if sender.relevance_score else 'N/A'}, "
                        f"type: {sender.sender_type}"
                    ),
                )
                db.add(item)

            await db.commit()

            return {
                "id": proposal.id,
                "type": "unsubscribe",
                "title": proposal.title,
                "affected_count": total_affected,
                "senders": [
                    {
                        "address": s.email_address,
                        "name": s.display_name,
                        "count": s.total_emails,
                        "relevance": round(s.relevance_score, 2) if s.relevance_score else None,
                    }
                    for s in low_engagement_senders
                ],
            }

    async def generate_archive_proposals(self) -> Optional[dict]:
        """Find old read emails that can be archived."""
        async with async_session() as db:
            # Find read emails older than 30 days in noise/transactional categories
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)

            archivable_query = (
                select(func.count(Email.id))
                .join(EmailClassification, Email.id == EmailClassification.email_id)
                .where(
                    and_(
                        Email.is_read == True,
                        Email.date_sent < cutoff,
                        EmailClassification.category.in_(["noise", "transactional", "notification", "marketing"]),
                    )
                )
            )
            archivable_count = (await db.execute(archivable_query)).scalar() or 0

            if archivable_count < 5:
                return None

            # Category breakdown
            breakdown_query = (
                select(
                    EmailClassification.category,
                    func.count(Email.id),
                )
                .join(Email, Email.id == EmailClassification.email_id)
                .where(
                    and_(
                        Email.is_read == True,
                        Email.date_sent < cutoff,
                        EmailClassification.category.in_(["noise", "transactional", "notification", "marketing"]),
                    )
                )
                .group_by(EmailClassification.category)
            )
            breakdown = {row[0]: row[1] for row in (await db.execute(breakdown_query)).all()}

            # Create proposal
            proposal = CleanupProposal(
                proposal_type="archive",
                title=f"Archive {archivable_count} old read emails (30+ days)",
                description=(
                    f"Found {archivable_count} read emails older than 30 days in "
                    f"low-priority categories. Breakdown: "
                    + ", ".join(f"{cat}: {count}" for cat, count in breakdown.items())
                ),
                affected_count=archivable_count,
                affected_query={
                    "type": "old_read_emails",
                    "older_than_days": 30,
                    "categories": ["noise", "transactional", "notification", "marketing"],
                },
                proposed_action={"action": "archive"},
                status="pending",
            )
            db.add(proposal)
            await db.commit()

            return {
                "id": proposal.id,
                "type": "archive",
                "title": proposal.title,
                "affected_count": archivable_count,
                "breakdown": breakdown,
            }

    async def generate_extraction_proposals(self) -> Optional[dict]:
        """Find high-value unextracted links — propose extraction."""
        async with async_session() as db:
            # Find high-relevance links that haven't been extracted
            result = await db.execute(
                select(ExtractedLink, Email)
                .join(Email, Email.id == ExtractedLink.email_id)
                .where(
                    and_(
                        ExtractedLink.relevance_score >= 0.6,
                        ExtractedLink.pipeline_status == "pending",
                    )
                )
                .order_by(ExtractedLink.relevance_score.desc())
                .limit(50)
            )
            rows = result.all()

            if not rows:
                return None

            links_data = []
            for link, email_obj in rows:
                links_data.append({
                    "url": link.url,
                    "domain": link.domain,
                    "type": link.link_type,
                    "relevance": round(link.relevance_score, 2) if link.relevance_score else 0,
                    "from_subject": email_obj.subject[:60] if email_obj.subject else "(no subject)",
                })

            # Create proposal
            proposal = CleanupProposal(
                proposal_type="extraction",
                title=f"Extract {len(links_data)} high-value links into content pipeline",
                description=(
                    f"Found {len(links_data)} links with relevance >= 0.6 that haven't been "
                    f"extracted into the content pipeline yet. These are from emails with "
                    f"potentially valuable articles, repos, or papers."
                ),
                affected_count=len(links_data),
                affected_query={
                    "type": "high_value_links",
                    "min_relevance": 0.6,
                    "status": "pending",
                },
                proposed_action={"action": "extract_to_pipeline"},
                status="pending",
            )
            db.add(proposal)

            # Add items for each link
            for link, email_obj in rows:
                item = ProposalItem(
                    proposal_id=proposal.id,
                    email_id=email_obj.id,
                    action="extract",
                    reason=f"[{link.link_type}] rel={link.relevance_score:.2f}: {link.url[:80]}",
                )
                db.add(item)

            await db.commit()

            return {
                "id": proposal.id,
                "type": "extraction",
                "title": proposal.title,
                "affected_count": len(links_data),
                "links": links_data[:10],  # Preview first 10
            }

    async def approve_proposal(self, proposal_id: int) -> dict:
        """Approve a proposal — marks it as approved, ready for execution."""
        async with async_session() as db:
            proposal = await db.get(CleanupProposal, proposal_id)
            if not proposal:
                return {"error": "Proposal not found"}

            if proposal.status != "pending":
                return {"error": f"Proposal is {proposal.status}, not pending"}

            proposal.status = "approved"
            proposal.reviewed_at = datetime.now(timezone.utc)
            await db.commit()

            return {"id": proposal_id, "status": "approved"}

    async def reject_proposal(self, proposal_id: int) -> dict:
        """Reject a proposal."""
        async with async_session() as db:
            proposal = await db.get(CleanupProposal, proposal_id)
            if not proposal:
                return {"error": "Proposal not found"}

            proposal.status = "rejected"
            proposal.reviewed_at = datetime.now(timezone.utc)
            await db.commit()

            return {"id": proposal_id, "status": "rejected"}

    async def list_proposals(self, status: Optional[str] = None) -> list[dict]:
        """List all proposals with optional status filter."""
        async with async_session() as db:
            query = select(CleanupProposal).order_by(CleanupProposal.created_at.desc())
            if status:
                query = query.where(CleanupProposal.status == status)

            result = await db.execute(query)
            proposals = result.scalars().all()

            return [
                {
                    "id": p.id,
                    "type": p.proposal_type,
                    "title": p.title,
                    "description": p.description,
                    "affected_count": p.affected_count,
                    "status": p.status,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
                }
                for p in proposals
            ]


# Singleton
proposal_engine = ProposalEngine()
