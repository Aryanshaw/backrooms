import enum
from config.db import Base

from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Integer
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
    updated_at = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now)

    members = relationship(
        "RoomMember", back_populates="room", cascade="all, delete-orphan"
    )
    activities = relationship(
        "RoomActivity", back_populates="room", cascade="all, delete-orphan"
    )
    room_metadata = relationship(
        "RoomMetadata", back_populates="room", cascade="all, delete-orphan"
    )
    room_summaries = relationship(
        "RoomSummaries", back_populates="room", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "owner_id": self.owner_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_active": self.last_active,
        }

    def update_timestamp(self):
        self.updated_at = datetime.now()

    def get_members(self, active_only: bool = False):
        members = self.members
        if active_only:
            members = [member for member in members if member.is_active]
        return [member.to_dict() for member in members]


    def get_activities(self):
        return [activity.to_dict() for activity in self.activities]


class RoomMember(Base):
    __tablename__ = "room_members"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uix_room_member_user"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(String, nullable=False)
    joined_at = Column(DateTime, default=datetime.now)
    status = Column(String, nullable=False, default="active")
    role = Column(String, nullable=False, default="member")
    room = relationship("Room", back_populates="members")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def to_dict(self):
        return {
            "id": str(self.id),
            "room_id": str(self.room_id),
            "user_id": self.user_id,
            "joined_at": self.joined_at,
            "status": self.status,
            "role": self.role,
        }


class RoomActivityTypes(str, enum.Enum):
    ROOM_CREATED = "room_created"
    ROOM_DELETED = "room_deleted"
    ROOM_RENAMED = "room_renamed"

    MEMBER_JOINED = "member_joined"
    MEMBER_LEFT = "member_left"
    MEMBER_REMOVED = "member_removed"

    INVITE_CREATED = "invite_created"
    INVITE_ACCEPTED = "invite_accepted"
    INVITE_REVOKED = "invite_revoked"

    MESSAGE_SENT = "message_sent"
    MESSAGE_EDITED = "message_edited"
    MESSAGE_DELETED = "message_deleted"

    FILE_UPLOADED = "file_uploaded"
    FILE_DELETED = "file_deleted"

    ROOM_ARCHIVED = "room_archived"
    ROOM_UNARCHIVED = "room_unarchived"

    SETTINGS_UPDATED = "settings_updated"

    ACCESS_GRANTED = "access_granted"
    ACCESS_REVOKED = "access_revoked"

    SUMMARY_CREATED = "summary_created"


class RoomActivity(Base):
    __tablename__ = "room_activity"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(String, nullable=False)
    activity_type = Column(
        String, nullable=False
    )  # "room_created", "member_joined", etc.
    activity_log = Column(String, nullable=True)  # any extra context
    created_at = Column(DateTime, default=datetime.now)
    room = relationship("Room", back_populates="activities")

    def to_dict(self):
        return {
            "id": str(self.id),
            "room_id": str(self.room_id),
            "user_id": self.user_id,
            "activity_type": self.activity_type,
            "activity_log": self.activity_log,
            "created_at": str(self.created_at),
        }


class RoomMetadata(Base):
    __tablename__ = "room_metadata"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id = Column(
        UUID(as_uuid=True), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    custom_instructions = Column(String, nullable=True)
    invite_version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.now)
    room = relationship("Room", back_populates="room_metadata")

    def to_dict(self):
        return {
            "id": str(self.id),
            "room_id": str(self.room_id),
            "custom_instructions": self.custom_instructions,
            "invite_version": int(self.invite_version),
            "created_at": str(self.created_at)
        }
