"""Cleanup proposal models — AI-generated inbox cleanup actions."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CleanupProposal(Base):
    __tablename__ = "cleanup_proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_type: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    title: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    affected_count: Mapped[Optional[int]] = mapped_column(Integer)
    affected_query: Mapped[Optional[dict]] = mapped_column(JSON)
    proposed_action: Mapped[Optional[dict]] = mapped_column(JSON)

    # Status
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Items
    items: Mapped[list["ProposalItem"]] = relationship(
        back_populates="proposal", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Proposal {self.id}: {self.proposal_type} ({self.status})>"


class ProposalItem(Base):
    __tablename__ = "proposal_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    proposal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cleanup_proposals.id", ondelete="CASCADE"), index=True
    )
    email_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("emails.id", ondelete="SET NULL")
    )
    sender_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("sender_profiles.id", ondelete="SET NULL")
    )

    action: Mapped[Optional[str]] = mapped_column(String(32))
    reason: Mapped[Optional[str]] = mapped_column(Text)
    item_status: Mapped[str] = mapped_column(String(32), default="pending")

    # Relationships
    proposal: Mapped["CleanupProposal"] = relationship(back_populates="items")

    def __repr__(self):
        return f"<ProposalItem {self.id}: {self.action} ({self.item_status})>"
