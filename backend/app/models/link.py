"""Extracted link model — URLs found in emails with AI scoring."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Float, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExtractedLink(Base):
    __tablename__ = "extracted_links"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("emails.id", ondelete="CASCADE"), index=True
    )

    # Link data
    url: Mapped[str] = mapped_column(Text, nullable=False)
    anchor_text: Mapped[Optional[str]] = mapped_column(Text)
    domain: Mapped[Optional[str]] = mapped_column(String(256), index=True)
    link_type: Mapped[Optional[str]] = mapped_column(String(64))  # article, github, arxiv, video, tool

    # Scoring
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, index=True)

    # Pipeline integration
    pipeline_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    pipeline_result: Mapped[Optional[dict]] = mapped_column(JSON)

    # Meta
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    email: Mapped["Email"] = relationship(back_populates="links")

    def __repr__(self):
        return f"<Link {self.id}: {self.domain} ({self.pipeline_status})>"
