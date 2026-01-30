"""API routes for Content Bridge — Email → Extraction Pipeline → ML integration."""

from fastapi import APIRouter

from app.services.content_bridge import content_bridge

router = APIRouter(prefix="/api/content", tags=["content-bridge"])


@router.get("/intelligence")
async def content_intelligence():
    """Get content intelligence report — what's in the inbox worth extracting."""
    return await content_bridge.get_content_intelligence()


@router.post("/classify")
async def classify_links(min_relevance: float = 0.3):
    """Scan and classify all pending links by content type."""
    return await content_bridge.scan_and_classify_links(min_relevance)


@router.post("/extract")
async def run_extraction(
    min_relevance: float = 0.5,
    limit_per_type: int = 20,
    dry_run: bool = True,
):
    """Run the extraction pipeline: classify → dispatch to Extraction Gateway → track.

    Set dry_run=false to actually dispatch to extractors.
    """
    return await content_bridge.run_extraction_pipeline(
        min_relevance=min_relevance,
        limit_per_type=limit_per_type,
        dry_run=dry_run,
    )


@router.post("/classify-url")
async def classify_single_url(url: str):
    """Classify a single URL for debugging/testing."""
    return content_bridge.classify_link(url)
