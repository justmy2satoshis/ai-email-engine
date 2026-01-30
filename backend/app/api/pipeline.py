"""Pipeline integration API endpoints."""

from fastapi import APIRouter, Query
from typing import Optional

from app.services.pipeline_adapter import pipeline_adapter

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/queue")
async def queue_for_extraction(
    min_relevance: float = Query(0.5, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=500),
):
    """Queue high-relevance pending links for extraction."""
    return await pipeline_adapter.queue_links_for_extraction(
        min_relevance=min_relevance,
        limit=limit,
    )


@router.get("/queue")
async def get_queue():
    """Get current extraction queue."""
    return await pipeline_adapter.get_extraction_queue()


@router.post("/extracted/{link_id}")
async def mark_extracted(link_id: int, result: Optional[dict] = None):
    """Mark a link as successfully extracted."""
    success = await pipeline_adapter.mark_extracted(link_id, result)
    if success:
        return {"status": "ok", "link_id": link_id}
    return {"status": "error", "detail": "Link not found"}


@router.get("/stats")
async def pipeline_stats():
    """Get pipeline integration statistics."""
    return await pipeline_adapter.get_pipeline_stats()
