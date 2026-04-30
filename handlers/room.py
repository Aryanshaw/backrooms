import os
from datetime import datetime
from typing import Optional
import uuid
from config.logger import get_logger
from models.rooms import Room, RoomActivity, RoomActivityTypes, RoomMember, RoomMetadata
from models.message import RoomSummaries
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = get_logger(__name__)


class RoomHandler:
    def __init__(self, db):
        """Store the shared DB connection wrapper used by room queries."""
        self.db = db

    async def create_room(self, name: str, user_id: str):
        """Create a room, register the owner membership, and log creation."""
        try:
            room_id = str(uuid.uuid4())
            room_activity_id = str(uuid.uuid4())
            room_member_id = str(uuid.uuid4())
            async with self.db.session() as session:
                # create a new room
                room = Room(id=room_id, name=name, owner_id=user_id)
                session.add(room)

                # mark the current user as the owner of the room
                room_member = RoomMember(id=room_member_id, room_id=room_id, user_id=user_id, joined_at=datetime.now(), status="active", role="owner")
                session.add(room_member)

                # create a new activity log that a new room was added
                room_activity = RoomActivity(
                    id=room_activity_id,
                    room_id=room_id,
                    user_id=user_id,
                    activity_type=RoomActivityTypes.ROOM_CREATED,
                    activity_log=f"[ROOM CREATED]-> new room of id: {room_id}, name: {room.name} was created",
                )
                session.add(room_activity)

                # create a new metadata row for the room
                room_metadata = RoomMetadata(id=str(uuid.uuid4()), room_id=room_id, invite_version=1,)
                session.add(room_metadata)

                await session.commit()

            return {"room_id": room_id}
        except Exception as e:
            logger.error(f"Failed to create room: {str(e)}")
            raise Exception from e

    async def get_room(self, room_id: str, user_id: str) -> Optional[dict]:
        """Return room details when the user is the owner or an active member."""
        try:
            async with self.db.session() as session:
                result = await session.execute(
                    select(Room)
                    .options(
                        selectinload(Room.members),
                        selectinload(Room.activities)
                    )
                    .where(
                        Room.id == room_id,
                    )
                )

                room = result.scalar_one_or_none()

                if not room:
                    logger.error(
                        f"Room not found for user: {user_id} and room_id: {room_id}"
                    )

                    return {
                        "members": [],
                        "activities": [],
                        "room": None,
                        "summary": None,
                    }

                # fetch latest summary for this room if one exists
                summary_result = await session.execute(
                    select(RoomSummaries)
                    .where(RoomSummaries.room_id == room_id)
                    .order_by(RoomSummaries.created_at.desc())
                    .limit(1)
                )
                latest_summary = summary_result.scalar_one_or_none()

                has_access = room.owner_id == user_id or any(
                    member.user_id == user_id and member.is_active for member in room.members
                )
                if not has_access:
                    logger.error(
                        f"Room access denied for user: {user_id} and room_id: {room_id}"
                    )
                    return {
                        "members": [],
                        "activities": [],
                        "room": None,
                        "summary": None,
                    }

                return {
                    "members": room.get_members(active_only=True),
                    "activities": room.get_activities(),
                    "room": room.to_dict(),
                    "summary": latest_summary.summary if latest_summary else None,
                }

        except Exception as e:
            logger.error(f"Failed to get room: {str(e)}")
            raise Exception from e

    async def get_room_by_id(self, room_id: str) -> Optional[dict]:
        """Return room details without applying per-user access checks."""
        try:
            async with self.db.session() as session:
                result = await session.execute(
                    select(Room)
                    .options(
                        selectinload(Room.members),
                        selectinload(Room.activities)
                    )
                    .where(Room.id == room_id)
                )
                room = result.scalar_one_or_none()
                if not room:
                    return None

                return {
                    "members": room.get_members(active_only=True),
                    "activities": room.get_activities(),
                    "room": room.to_dict(),
                }
        except Exception as e:
            logger.error(f"Failed to get room by id: {str(e)}")
            raise Exception from e

    async def user_owns_room(self, room_id: str, user_id: str) -> bool:
        """Check whether the given user is the owner of the room."""
        try:
            async with self.db.session() as session:
                result = await session.execute(
                    select(Room.id).where(Room.id == room_id, Room.owner_id == user_id)
                )
                return result.scalar_one_or_none() is not None
        except Exception as e:
            logger.error(f"Failed to verify room ownership: {str(e)}")
            raise Exception from e

    async def list_rooms(self, user_id: str) -> list[dict]:
        """List rooms where the user currently has an active membership."""
        try:
            async with self.db.session() as session:
                result = await session.execute(
                    select(Room)
                    .join(RoomMember, RoomMember.room_id == Room.id)
                    .options(selectinload(Room.members))
                    .where(RoomMember.user_id == user_id, RoomMember.status == "active")
                    .order_by(Room.last_active.desc())
                )
                rooms = result.scalars().unique().all()

            return [
                {
                    "id": str(room.id),
                    "name": room.name,
                    "owner_id": room.owner_id,
                    "created_at": room.created_at.isoformat(),
                    "last_active": room.last_active.isoformat(),
                    "member_count": len([member for member in room.members if member.is_active]),
                }
                for room in rooms
            ]
        except Exception as e:
            logger.error(f"Failed to list rooms: {str(e)}")
            raise Exception from e
    
    async def join_room(self, room_id: str, user_id: str) -> bool:
        """Activate or create a membership row for the user in the room."""
        try:
            async with self.db.session() as session:
                result = await session.execute(
                    select(RoomMember)
                    .where(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
                )
                room_member = result.scalar_one_or_none()

                if room_member:
                    room_member.status = "active"
                    room_member.joined_at = datetime.now()
                    room_member.updated_at = datetime.now()
                else:
                    room_result = await session.execute(
                        select(Room.owner_id).where(Room.id == room_id)
                    )
                    owner_id = room_result.scalar_one_or_none()
                    role = "owner" if owner_id == user_id else "member"
                    room_member = RoomMember(id=str(uuid.uuid4()), room_id=room_id, user_id=user_id, joined_at=datetime.now(), status="active", role=role)
                    session.add(room_member)

                room_result = await session.execute(
                    select(Room)
                    .where(Room.id == room_id)
                )
                room = room_result.scalar_one_or_none()
                if room:
                    room.last_active = datetime.now()
                    room.updated_at = datetime.now()

                await session.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to join room: {str(e)}")
            raise Exception from e

    async def bump_invite_version(self, room_id: str, user_id: str) -> Optional[dict]:
        """Increment invite_version for an owner to revoke older invite tokens."""
        try:
            async with self.db.session() as session:
                result = await session.execute(
                    select(Room).where(Room.id == room_id, Room.owner_id == user_id)
                )
                room = result.scalar_one_or_none()
                if not room:
                    return None

                # fetch existing metadata row; create if missing (though it should exist now)
                metadata_result = await session.execute(
                    select(RoomMetadata).where(RoomMetadata.room_id == room_id)
                )
                metadata = metadata_result.scalar_one_or_none()
                
                if not metadata:
                    metadata = RoomMetadata(id=str(uuid.uuid4()), room_id=room_id, invite_version=1,)
                    session.add(metadata)
                
                metadata.invite_version += 1
                room.updated_at = datetime.now()
                room.last_active = datetime.now()
                await session.commit()
                await session.refresh(room)
                await session.refresh(metadata)

                return {
                    "id": str(room.id),
                    "invite_version": metadata.invite_version
                }
        except Exception as e:
            logger.error(f"Failed to bump invite version: {str(e)}")
            raise Exception from e

    async def exit_room(self, room_id: str, user_id: str) -> bool:
        """Soft-exit the user from a room by marking active memberships inactive."""
        try:
            async with self.db.session() as session:
                result = await session.execute(
                    select(RoomMember)
                    .where(RoomMember.room_id == room_id, RoomMember.user_id == user_id, RoomMember.status == "active")
                )
                room_member = result.scalar_one_or_none()
                if not room_member:
                    return False

                now = datetime.now()
                room_member.status = "inactive"
                room_member.updated_at = now

                room_result = await session.execute(
                    select(Room).where(Room.id == room_id)
                )
                room = room_result.scalar_one_or_none()
                if room:
                    room.last_active = now
                    room.updated_at = now

                await session.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to exit room: {str(e)}")
            raise Exception from e

    async def log_room_activity(self, room_id: str, user_id: str, activity_type: str , activity_log: str):
        """Append a room activity entry for audit and timeline visibility."""
        try:
            async with self.db.session() as session:
                room_activity = RoomActivity(
                    id=str(uuid.uuid4()),
                    room_id=room_id,
                    user_id=user_id,
                    activity_type=activity_type,
                    activity_log=activity_log,
                )
                session.add(room_activity)
                await session.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to log room activity: {str(e)}")
            raise Exception from e

    async def generate_invite(self, room_id: str, user_id: str) -> Optional[str]:
        """Bump version, log activity, and return signed token."""
        try:
            bump_data = await self.bump_invite_version(room_id, user_id)
            if not bump_data:
                return None

            invite_secret = os.getenv("BACKROOMS_INVITE_SECRET")
            if not invite_secret:
                raise Exception("BACKROOMS_INVITE_SECRET is not set in environment.")

            from tools.room_management.utils.invite_tokens import sign_invite_token
            token = sign_invite_token(secret=invite_secret, room_id=str(bump_data.get("id")), version=bump_data.get("invite_version"))
            
            activity_log = f"[INVITE GENERATED]-> user_id: {user_id} generated invite for room_id: {room_id} version: {bump_data.get('invite_version')}"
            await self.log_room_activity(room_id, user_id, RoomActivityTypes.INVITE_CREATED.value, activity_log)
            
            return token
        except Exception as e:
            logger.error(f"Failed to generate invite: {str(e)}")
            raise Exception from e
