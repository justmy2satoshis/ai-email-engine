"""Email classification model — AI-generated categories and scores."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Float, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EmailClassification(Base):
    __tablename__ = "email_classifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("emails.id", ondelete="CASCADE"), index=True
    )

    # Classification
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    topics: Mapped[Optional[dict]] = mapped_column(JSON)  # ['crypto', 'ml_research']
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, index=True)
    summary: Mapped[Optional[str]] = mapped_column(Text)

    # Meta
    classified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    model_used: Mapped[Optional[str]] = mapped_column(String(64))

    # Relationships
    email: Mapped["Email"] = relationship(back_populates="classifications")

    def __repr__(self):
        return f"<Classification {self.id}: {self.category} ({self.confidence:.2f})>"
