from datetime import datetime
from typing import Optional
import uuid
from config.logger import get_logger
from models.rooms import Room, RoomActivity, RoomActivityTypes, RoomMember
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = get_logger(__name__)


class RoomHanler:
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
                room_member = RoomMember(id=room_member_id, room_id=room_id, user_id=user_id, joined_at=datetime.now())
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
                        "room": None
                    }

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
                        "room": None
                    }

                return {
                    "members": room.get_members(),
                    "activities": room.get_activities(),
                    "room": room.to_dict()
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
                    .where(RoomMember.user_id == user_id)
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
                    "member_count": len(room.members),
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
                room_member = RoomMember(id=str(uuid.uuid4()), room_id=room_id, user_id=user_id, joined_at=datetime.now())
                session.add(room_member)
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

                room.invite_version += 1
                room.updated_at = datetime.now()
                room.last_active = datetime.now()
                await session.commit()
                await session.refresh(room)

                return room.to_dict()
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
                room_members = result.scalars().all()
                if not room_members:
                    return False

                now = datetime.now()
                for room_member in room_members:
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
