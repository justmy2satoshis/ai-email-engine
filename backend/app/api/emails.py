"""Email API endpoints — browse synced emails."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.email import Email

router = APIRouter(prefix="/api/emails", tags=["emails"])


class EmailSummary(BaseModel):
    id: int
    message_id: str
    folder: str
    from_address: Optional[str]
    from_name: Optional[str]
    subject: Optional[str]
    date_sent: Optional[datetime]
    is_read: bool
    is_starred: bool
    has_attachments: bool
    size_bytes: Optional[int]

    class Config:
        from_attributes = True


class EmailDetail(EmailSummary):
    to_addresses: Optional[list]
    cc_addresses: Optional[list]
    body_text: Optional[str]
    body_html: Optional[str]
    date_synced: Optional[datetime]
    raw_headers: Optional[dict]

    class Config:
        from_attributes = True


class EmailListResponse(BaseModel):
    emails: list[EmailSummary]
    total: int
    page: int
    page_size: int


@router.get("/", response_model=EmailListResponse)
async def list_emails(
    folder: Optional[str] = None,
    from_address: Optional[str] = None,
    search: Optional[str] = None,
    is_read: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List emails with optional filters and pagination."""
    query = select(Email)

    # Apply filters
    if folder:
        query = query.where(Email.folder == folder)
    if from_address:
        query = query.where(Email.from_address.ilike(f"%{from_address}%"))
    if search:
        query = query.where(
            Email.subject.ilike(f"%{search}%") | Email.from_name.ilike(f"%{search}%")
        )
    if is_read is not None:
        query = query.where(Email.is_read == is_read)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate and order
    query = query.order_by(desc(Email.date_sent))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    emails = result.scalars().all()

    return EmailListResponse(
        emails=[EmailSummary.model_validate(e) for e in emails],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats")
async def email_stats(db: AsyncSession = Depends(get_db)):
    """Get email statistics."""
    total = (await db.execute(select(func.count(Email.id)))).scalar() or 0
    unread = (await db.execute(
        select(func.count(Email.id)).where(Email.is_read == False)
    )).scalar() or 0

    # Emails by folder
    folder_query = select(
        Email.folder, func.count(Email.id)
    ).group_by(Email.folder)
    folder_result = await db.execute(folder_query)
    by_folder = {row[0]: row[1] for row in folder_result.all()}

    # Top senders
    sender_query = select(
        Email.from_address, func.count(Email.id).label("count")
    ).group_by(Email.from_address).order_by(desc("count")).limit(20)
    sender_result = await db.execute(sender_query)
    top_senders = [
        {"address": row[0], "count": row[1]}
        for row in sender_result.all()
    ]

    return {
        "total": total,
        "unread": unread,
        "by_folder": by_folder,
        "top_senders": top_senders,
    }


@router.get("/{email_id}", response_model=EmailDetail)
async def get_email(email_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single email by ID with full details."""
    result = await db.execute(select(Email).where(Email.id == email_id))
    email_obj = result.scalar_one_or_none()

    if not email_obj:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Email not found")

    return EmailDetail.model_validate(email_obj)
