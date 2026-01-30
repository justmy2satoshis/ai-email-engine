"""Classification and processing API endpoints."""

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.classification import EmailClassification
from app.models.link import ExtractedLink
from app.models.sender import SenderProfile
from app.services.processor import email_processor

router = APIRouter(prefix="/api", tags=["classification"])


# --- Processing ---

class ProcessResult(BaseModel):
    processed: int
    errors: int
    links_found: int = 0


@router.post("/process", response_model=ProcessResult)
async def process_emails(limit: int = Query(50, ge=1, le=500)):
    """Process unclassified emails with AI (classify + extract links)."""
    result = await email_processor.process_unclassified(limit=limit)
    return ProcessResult(**result)


@router.post("/process/{email_id}")
async def process_single_email(email_id: int):
    """Process a specific email by ID."""
    result = await email_processor.process_email_by_id(email_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Email not found")
    return result


@router.get("/process/stats")
async def processing_stats():
    """Get processing statistics."""
    return await email_processor.get_processing_stats()


# --- Links ---

class LinkResponse(BaseModel):
    id: int
    email_id: int
    url: str
    domain: Optional[str]
    link_type: Optional[str]
    relevance_score: Optional[float]
    pipeline_status: str
    extracted_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("/links", response_model=list[LinkResponse])
async def list_links(
    min_relevance: float = Query(0.0, ge=0.0, le=1.0),
    pipeline_status: Optional[str] = None,
    link_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List extracted links with filtering."""
    query = select(ExtractedLink).where(
        ExtractedLink.relevance_score >= min_relevance
    )

    if pipeline_status:
        query = query.where(ExtractedLink.pipeline_status == pipeline_status)
    if link_type:
        query = query.where(ExtractedLink.link_type == link_type)

    query = query.order_by(desc(ExtractedLink.relevance_score)).limit(limit)
    result = await db.execute(query)
    return [LinkResponse.model_validate(l) for l in result.scalars().all()]


@router.patch("/links/{link_id}/status")
async def update_link_status(
    link_id: int,
    status: str = Query(..., description="New status: pending, queued, extracted, skipped"),
    db: AsyncSession = Depends(get_db),
):
    """Update a link's pipeline status."""
    link = await db.get(ExtractedLink, link_id)
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    link.pipeline_status = status
    await db.commit()
    return {"id": link_id, "pipeline_status": status}


# --- Senders ---

class SenderResponse(BaseModel):
    id: int
    email_address: str
    display_name: Optional[str]
    sender_type: Optional[str]
    total_emails: int
    emails_opened: int
    relevance_score: Optional[float]
    suggested_action: Optional[str]
    first_seen: Optional[datetime]
    last_seen: Optional[datetime]

    class Config:
        from_attributes = True


@router.get("/senders", response_model=list[SenderResponse])
async def list_senders(
    sender_type: Optional[str] = None,
    sort_by: str = Query("total_emails", description="Sort by: total_emails, relevance_score, last_seen"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List sender profiles with sorting."""
    query = select(SenderProfile)

    if sender_type:
        query = query.where(SenderProfile.sender_type == sender_type)

    # Sort
    if sort_by == "relevance_score":
        query = query.order_by(desc(SenderProfile.relevance_score))
    elif sort_by == "last_seen":
        query = query.order_by(desc(SenderProfile.last_seen))
    else:
        query = query.order_by(desc(SenderProfile.total_emails))

    query = query.limit(limit)
    result = await db.execute(query)
    return [SenderResponse.model_validate(s) for s in result.scalars().all()]
