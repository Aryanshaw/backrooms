import enum
from config.db import Base

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

class Messages(Base):
    __tablename__ = "messages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(String, nullable=False)
    message_type = Column(
        String, nullable=False
    )  # "user", "assistant", "system", etc.
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    room = relationship("Room", back_populates="messages")

    def to_dict(self):
        return {
            "id": str(self.id),
            "room_id": str(self.room_id),
            "user_id": self.user_id,
            "message_type": self.message_type,
            "content": self.content,
            "created_at": str(self.created_at),
        }

class RoomSummaries(Base):
    __tablename__ = "room_summaries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    summary = Column(String, nullable=False)
    from_message_id = Column(String, nullable=False)
    to_message_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    room = relationship("Room", back_populates="room_summaries")

    def to_dict(self):
        return {
            "id": str(self.id),
            "room_id": str(self.room_id),
            "summary": self.summary,
            "from_message_id": self.from_message_id,
            "to_message_id": self.to_message_id,
            "created_at": str(self.created_at),
        }