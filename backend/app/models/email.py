"""Email model — core storage for synced emails."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Boolean, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Email(Base):
    __tablename__ = "emails"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    uid: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    folder: Mapped[str] = mapped_column(String(128), default="INBOX", index=True)

    # Addresses
    from_address: Mapped[Optional[str]] = mapped_column(String(256), index=True)
    from_name: Mapped[Optional[str]] = mapped_column(String(256))
    to_addresses: Mapped[Optional[dict]] = mapped_column(JSON)
    cc_addresses: Mapped[Optional[dict]] = mapped_column(JSON)
    reply_to: Mapped[Optional[str]] = mapped_column(String(256))

    # Content
    subject: Mapped[Optional[str]] = mapped_column(Text)
    body_text: Mapped[Optional[str]] = mapped_column(Text)
    body_html: Mapped[Optional[str]] = mapped_column(Text)

    # Metadata
    date_sent: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    date_received: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    date_synced: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_starred: Mapped[bool] = mapped_column(Boolean, default=False)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    raw_headers: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationships
    classifications: Mapped[list["EmailClassification"]] = relationship(
        back_populates="email", cascade="all, delete-orphan"
    )
    links: Mapped[list["ExtractedLink"]] = relationship(
        back_populates="email", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Email {self.id}: {self.subject[:50] if self.subject else '(no subject)'}>"
