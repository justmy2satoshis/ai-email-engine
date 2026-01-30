"""Sender profile model — intelligence about email senders."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SenderProfile(Base):
    __tablename__ = "sender_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_address: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(256))

    # Classification
    sender_type: Mapped[Optional[str]] = mapped_column(String(64))  # newsletter, service, person, marketing

    # Stats
    total_emails: Mapped[int] = mapped_column(Integer, default=0)
    emails_opened: Mapped[int] = mapped_column(Integer, default=0)
    emails_acted_on: Mapped[int] = mapped_column(Integer, default=0)
    links_extracted: Mapped[int] = mapped_column(Integer, default=0)

    # Timeline
    first_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Intelligence
    relevance_score: Mapped[Optional[float]] = mapped_column(Float)
    suggested_action: Mapped[Optional[str]] = mapped_column(String(32))  # keep, unsubscribe, filter, archive

    # Meta
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    def __repr__(self):
        return f"<Sender {self.email_address}: {self.sender_type} (rel={self.relevance_score})>"
