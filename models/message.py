from config.db import Base

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid


class RoomSummaries(Base):
    __tablename__ = "room_summaries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    summary = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    room = relationship("Room", back_populates="room_summaries")

    def to_dict(self):
        return {
            "id": str(self.id),
            "room_id": str(self.room_id),
            "summary": self.summary,
            "created_at": str(self.created_at),
        }
