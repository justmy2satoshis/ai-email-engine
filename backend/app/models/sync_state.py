"""Sync state tracking — knows where we left off per folder."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SyncState(Base):
    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    folder: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    last_uid: Mapped[int] = mapped_column(Integer, default=0)
    last_sync: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    total_synced: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self):
        return f"<SyncState {self.folder}: uid={self.last_uid}, total={self.total_synced}>"
