"""
Content Bridge — connects email-extracted links to the Knowledge Base extraction pipeline.

This is the key integration point: Email Engine → Content Pipeline → ML System.

Flow:
1. Email Engine classifies emails + extracts links with relevance scores
2. Content Bridge identifies high-value content links by type
3. Bridge dispatches to the Extraction Gateway (port 8250) for processing
4. Extracted content flows into Training Data Provider → VPS Data Router → ML
5. Results reported back to Email Engine for tracking

Integration points:
- Extraction Gateway: http://localhost:8250/extract/<name>
- Training Data Server: http://localhost:8301
- Qdrant: localhost:6333 (vector embeddings for extracted content)
"""

import logging
import asyncio
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse, unquote

import httpx
from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.link import ExtractedLink
from app.models.email import Email

logger = logging.getLogger(__name__)

# Extraction Gateway config
EXTRACTION_GATEWAY = "http://localhost:8250"

# Content type detection patterns
CONTENT_PATTERNS = {
    "medium": {
        "domains": [
            "medium.com", "towardsdatascience.com", "betterprogramming.pub",
            "levelup.gitconnected.com", "javascript.plainenglish.io",
            "python.plainenglish.io", "blog.devgenius.io",
            "ai.gopubby.com", "pub.towardsai.net",
        ],
        "extractor": "medium",
        "value": "high",  # Known ML/AI content source
    },
    "arxiv": {
        "domains": ["arxiv.org"],
        "url_patterns": [r"arxiv\.org/abs/\d+\.\d+", r"arxiv\.org/pdf/\d+\.\d+"],
        "extractor": "arxiv",
        "value": "high",
    },
    "github": {
        "domains": ["github.com"],
        "url_patterns": [r"github\.com/[\w-]+/[\w.-]+(?:/|$)"],  # Repos, not assets
        "extractor": "github",
        "value": "high",
    },
    "twitter": {
        "domains": ["twitter.com", "x.com"],
        "url_patterns": [r"(?:twitter|x)\.com/\w+/status/\d+"],  # Specific tweets/threads
        "extractor": "twitter",
        "value": "medium",
    },
    "hackernews": {
        "domains": ["news.ycombinator.com"],
        "extractor": "hackernews",
        "value": "medium",
    },
    "devto": {
        "domains": ["dev.to"],
        "extractor": "devto",
        "value": "medium",
    },
    "youtube": {
        "domains": ["youtube.com", "youtu.be"],
        "url_patterns": [r"(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+"],
        "extractor": None,  # No extractor yet — track for future
        "value": "medium",
    },
    "substack": {
        "url_patterns": [r"[\w-]+\.substack\.com"],
        "extractor": None,  # Future: blog extractor
        "value": "medium",
    },
    "research": {
        "domains": [
            "openreview.net", "paperswithcode.com", "aclweb.org",
            "proceedings.neurips.cc", "openai.com/research",
            "deepmind.google", "research.google",
        ],
        "extractor": None,  # Future: research paper extractor
        "value": "high",
    },
}

# Junk domains to always skip
JUNK_DOMAINS = {
    "unsubscribe.", "click.", "track.", "email.", "list-manage.com",
    "mailchimp.com", "sendgrid.net", "amazonses.com", "mandrillapp.com",
    "google.com/maps", "facebook.com", "instagram.com", "linkedin.com/feed",
    "apple.com/legal", "protonmail.com",
}


class ContentBridge:
    """Bridge between Email Engine extracted links and Knowledge Base content pipeline."""

    def classify_link(self, url: str) -> dict:
        """Classify a URL into a content type with extraction routing."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower().replace("www.", "")
            path = unquote(parsed.path.lower())

            # Check junk first
            for junk in JUNK_DOMAINS:
                if junk in domain or junk in url.lower():
                    return {"type": "junk", "extractor": None, "value": "none"}

            # Match against content patterns
            for content_type, config in CONTENT_PATTERNS.items():
                # Domain match
                for d in config.get("domains", []):
                    if domain == d or domain.endswith(f".{d}"):
                        return {
                            "type": content_type,
                            "extractor": config["extractor"],
                            "value": config["value"],
                        }

                # URL pattern match
                for pattern in config.get("url_patterns", []):
                    if re.search(pattern, url, re.IGNORECASE):
                        return {
                            "type": content_type,
                            "extractor": config["extractor"],
                            "value": config["value"],
                        }

            # Substack detection (subdomain pattern)
            if ".substack.com" in domain:
                return {"type": "substack", "extractor": None, "value": "medium"}

            return {"type": "generic", "extractor": None, "value": "low"}

        except Exception as e:
            logger.error(f"Error classifying {url}: {e}")
            return {"type": "unknown", "extractor": None, "value": "low"}

    async def scan_and_classify_links(self, min_relevance: float = 0.3) -> dict:
        """Scan all unclassified links and tag them with content types."""
        stats = {"total": 0, "by_type": {}, "by_value": {}}

        async with async_session() as db:
            query = (
                select(ExtractedLink)
                .where(
                    and_(
                        ExtractedLink.pipeline_status == "pending",
                        ExtractedLink.relevance_score >= min_relevance,
                    )
                )
                .order_by(ExtractedLink.relevance_score.desc())
            )
            result = await db.execute(query)
            links = result.scalars().all()

            for link in links:
                classification = self.classify_link(link.url)
                content_type = classification["type"]
                extractor = classification["extractor"]
                value = classification["value"]

                # Update link metadata
                link.link_type = content_type
                existing = link.pipeline_result or {}
                existing["content_classification"] = classification
                existing["classified_at"] = datetime.now(timezone.utc).isoformat()
                link.pipeline_result = existing

                # Auto-skip junk
                if content_type == "junk":
                    link.pipeline_status = "skipped"

                stats["total"] += 1
                stats["by_type"][content_type] = stats["by_type"].get(content_type, 0) + 1
                stats["by_value"][value] = stats["by_value"].get(value, 0) + 1

            await db.commit()

        return stats

    async def dispatch_to_extraction_gateway(
        self,
        content_type: str,
        urls: list[str],
        timeout: int = 600,
    ) -> dict:
        """Send URLs to the Extraction Gateway for processing."""
        extractor = CONTENT_PATTERNS.get(content_type, {}).get("extractor")
        if not extractor:
            return {"status": "skipped", "reason": f"No extractor for {content_type}"}

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{EXTRACTION_GATEWAY}/extract/{extractor}",
                    json={"urls": urls},
                )
                response.raise_for_status()
                return {
                    "status": "dispatched",
                    "extractor": extractor,
                    "url_count": len(urls),
                    "response": response.json(),
                }
        except httpx.ConnectError:
            logger.error(f"Extraction Gateway not reachable at {EXTRACTION_GATEWAY}")
            return {"status": "error", "reason": "Gateway unreachable"}
        except Exception as e:
            logger.error(f"Dispatch failed for {extractor}: {e}")
            return {"status": "error", "reason": str(e)}

    async def run_extraction_pipeline(
        self,
        min_relevance: float = 0.5,
        limit_per_type: int = 20,
        dry_run: bool = False,
    ) -> dict:
        """Full pipeline: classify links → dispatch to extractors → track results."""
        result = {
            "classified": 0,
            "dispatched": {},
            "skipped": {},
            "errors": [],
        }

        # Step 1: Classify any unclassified links
        classify_stats = await self.scan_and_classify_links(min_relevance=0.3)
        result["classified"] = classify_stats["total"]

        # Step 2: Get queued links grouped by extractor
        async with async_session() as db:
            query = (
                select(ExtractedLink)
                .where(
                    and_(
                        ExtractedLink.pipeline_status == "pending",
                        ExtractedLink.relevance_score >= min_relevance,
                        ExtractedLink.link_type.isnot(None),
                        ExtractedLink.link_type != "junk",
                        ExtractedLink.link_type != "generic",
                    )
                )
                .order_by(ExtractedLink.relevance_score.desc())
            )
            links_result = await db.execute(query)
            links = links_result.scalars().all()

            # Group by content type
            by_type: dict[str, list] = {}
            for link in links:
                ct = link.link_type or "unknown"
                if ct not in by_type:
                    by_type[ct] = []
                if len(by_type[ct]) < limit_per_type:
                    by_type[ct].append(link)

            # Step 3: Dispatch each group
            for content_type, type_links in by_type.items():
                urls = [l.url for l in type_links]
                link_ids = [l.id for l in type_links]

                if dry_run:
                    result["dispatched"][content_type] = {
                        "count": len(urls),
                        "urls": urls[:5],
                        "dry_run": True,
                    }
                    continue

                # Dispatch to gateway
                dispatch_result = await self.dispatch_to_extraction_gateway(
                    content_type, urls
                )

                if dispatch_result["status"] == "dispatched":
                    # Mark links as queued
                    await db.execute(
                        update(ExtractedLink)
                        .where(ExtractedLink.id.in_(link_ids))
                        .values(
                            pipeline_status="queued",
                        )
                    )
                    result["dispatched"][content_type] = dispatch_result
                elif dispatch_result["status"] == "skipped":
                    result["skipped"][content_type] = {
                        "count": len(urls),
                        "reason": dispatch_result["reason"],
                    }
                else:
                    result["errors"].append({
                        "type": content_type,
                        "error": dispatch_result["reason"],
                    })

            await db.commit()

        return result

    async def get_content_intelligence(self) -> dict:
        """Get intelligence about email-sourced content for the ML system."""
        async with async_session() as db:
            # Content type breakdown
            type_query = (
                select(
                    ExtractedLink.link_type,
                    func.count(ExtractedLink.id),
                    func.avg(ExtractedLink.relevance_score),
                )
                .where(ExtractedLink.link_type.isnot(None))
                .group_by(ExtractedLink.link_type)
                .order_by(func.count(ExtractedLink.id).desc())
            )
            type_result = await db.execute(type_query)
            by_type = [
                {
                    "type": row[0],
                    "count": row[1],
                    "avg_relevance": round(float(row[2] or 0), 3),
                }
                for row in type_result.all()
            ]

            # Top domains contributing content
            domain_query = (
                select(
                    ExtractedLink.domain,
                    func.count(ExtractedLink.id),
                    func.avg(ExtractedLink.relevance_score),
                )
                .where(
                    and_(
                        ExtractedLink.pipeline_status != "skipped",
                        ExtractedLink.domain.isnot(None),
                    )
                )
                .group_by(ExtractedLink.domain)
                .order_by(func.count(ExtractedLink.id).desc())
                .limit(20)
            )
            domain_result = await db.execute(domain_query)
            top_domains = [
                {
                    "domain": row[0],
                    "count": row[1],
                    "avg_relevance": round(float(row[2] or 0), 3),
                }
                for row in domain_result.all()
            ]

            # Pipeline status summary
            status_query = (
                select(
                    ExtractedLink.pipeline_status,
                    func.count(ExtractedLink.id),
                )
                .group_by(ExtractedLink.pipeline_status)
            )
            status_result = await db.execute(status_query)
            pipeline_status = {row[0]: row[1] for row in status_result.all()}

            # High-value content waiting to be extracted
            high_value_query = (
                select(func.count(ExtractedLink.id))
                .where(
                    and_(
                        ExtractedLink.pipeline_status == "pending",
                        ExtractedLink.relevance_score >= 0.7,
                    )
                )
            )
            hv_result = await db.execute(high_value_query)
            high_value_pending = hv_result.scalar() or 0

            return {
                "by_content_type": by_type,
                "top_domains": top_domains,
                "pipeline_status": pipeline_status,
                "high_value_pending": high_value_pending,
            }


# Singleton
content_bridge = ContentBridge()
