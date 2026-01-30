"""Pipeline adapter — connects extracted links to the existing content pipeline."""

import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.link import ExtractedLink

logger = logging.getLogger(__name__)

# Domain → extractor mapping (matches existing content_pipelines/)
EXTRACTOR_MAP = {
    # Medium articles
    "medium.com": "medium",
    "towardsdatascience.com": "medium",
    "betterprogramming.pub": "medium",
    "levelup.gitconnected.com": "medium",
    # GitHub
    "github.com": "github",
    # arXiv
    "arxiv.org": "arxiv",
    # Twitter/X
    "twitter.com": "twitter",
    "x.com": "twitter",
    # Hacker News
    "news.ycombinator.com": "hackernews",
    # Dev.to
    "dev.to": "devto",
    # General articles (fallback)
}


class PipelineAdapter:
    """Routes extracted links to appropriate content pipeline extractors."""

    def get_extractor_for_url(self, url: str) -> str:
        """Determine which extractor to use for a given URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace("www.", "")

            # Check exact domain match
            if domain in EXTRACTOR_MAP:
                return EXTRACTOR_MAP[domain]

            # Check subdomain match (e.g., blog.example.com)
            for known_domain, extractor in EXTRACTOR_MAP.items():
                if domain.endswith(known_domain):
                    return extractor

            return "generic"
        except Exception:
            return "generic"

    async def queue_links_for_extraction(
        self,
        min_relevance: float = 0.5,
        limit: int = 50,
    ) -> dict:
        """Queue pending high-relevance links for extraction."""
        result = {"queued": 0, "by_extractor": {}}

        async with async_session() as db:
            # Find pending links above threshold
            query = (
                select(ExtractedLink)
                .where(
                    and_(
                        ExtractedLink.pipeline_status == "pending",
                        ExtractedLink.relevance_score >= min_relevance,
                    )
                )
                .order_by(ExtractedLink.relevance_score.desc())
                .limit(limit)
            )
            links_result = await db.execute(query)
            links = links_result.scalars().all()

            for link in links:
                extractor = self.get_extractor_for_url(link.url)
                link.pipeline_status = "queued"
                link.pipeline_result = {
                    "extractor": extractor,
                    "queued_at": datetime.now(timezone.utc).isoformat(),
                }

                result["queued"] += 1
                result["by_extractor"][extractor] = result["by_extractor"].get(extractor, 0) + 1

            await db.commit()

        return result

    async def get_extraction_queue(self) -> list[dict]:
        """Get all queued links grouped by extractor."""
        async with async_session() as db:
            query = (
                select(ExtractedLink)
                .where(ExtractedLink.pipeline_status == "queued")
                .order_by(ExtractedLink.relevance_score.desc())
            )
            result = await db.execute(query)
            links = result.scalars().all()

            return [
                {
                    "id": link.id,
                    "url": link.url,
                    "domain": link.domain,
                    "link_type": link.link_type,
                    "relevance_score": link.relevance_score,
                    "extractor": (link.pipeline_result or {}).get("extractor", "unknown"),
                }
                for link in links
            ]

    async def mark_extracted(self, link_id: int, result_data: Optional[dict] = None) -> bool:
        """Mark a link as successfully extracted."""
        async with async_session() as db:
            link = await db.get(ExtractedLink, link_id)
            if not link:
                return False

            link.pipeline_status = "extracted"
            if result_data:
                existing = link.pipeline_result or {}
                existing.update(result_data)
                existing["extracted_at"] = datetime.now(timezone.utc).isoformat()
                link.pipeline_result = existing

            await db.commit()
            return True

    async def get_pipeline_stats(self) -> dict:
        """Get pipeline integration statistics."""
        async with async_session() as db:
            from sqlalchemy import func

            # Status breakdown
            status_query = select(
                ExtractedLink.pipeline_status,
                func.count(ExtractedLink.id),
            ).group_by(ExtractedLink.pipeline_status)
            status_result = await db.execute(status_query)
            by_status = {row[0]: row[1] for row in status_result.all()}

            # Domain breakdown of queued/pending
            domain_query = (
                select(
                    ExtractedLink.domain,
                    func.count(ExtractedLink.id),
                )
                .where(ExtractedLink.pipeline_status.in_(["pending", "queued"]))
                .group_by(ExtractedLink.domain)
                .order_by(func.count(ExtractedLink.id).desc())
                .limit(15)
            )
            domain_result = await db.execute(domain_query)
            by_domain = {row[0]: row[1] for row in domain_result.all() if row[0]}

            return {
                "by_status": by_status,
                "by_domain": by_domain,
            }


# Singleton
pipeline_adapter = PipelineAdapter()
