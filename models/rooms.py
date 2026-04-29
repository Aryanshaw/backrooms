from config.db import Base

from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uix_owner_room"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    owner_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now)
    agenda = Column(String, nullable=True)
    custom_instructions = Column(String, nullable=True)
    members = relationship(
        "RoomMember", back_populates="room", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "owner_id": self.owner_id,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "agenda": self.agenda,
            "custom_instructions": self.custom_instructions,
        }


class RoomMember(Base):
    __tablename__ = "room_members"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(String, nullable=False)
    tool = Column(String, nullable=False)
    joined_at = Column(DateTime, default=datetime.now)
    room = relationship("Room", back_populates="members")

    def to_dict(self):
        return {
            "id": self.id,
            "room_id": self.room_id,
            "user_id": self.user_id,
            "tool": self.tool,
            "joined_at": self.joined_at,
        }
