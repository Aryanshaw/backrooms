from datetime import datetime
from typing import Optional
import uuid
from config.logger import get_logger
from models.rooms import Room, RoomActivity, RoomActivityTypes, RoomMember
from models.message import RoomSummaries
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = get_logger(__name__)


class RoomHanler:
    def __init__(self, db):
        self.db = db

    async def create_room(self, name: str, user_id: str):
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

                await session.commit()

            return {"room_id": room_id}
        except Exception as e:
            logger.error(f"Failed to create room: {str(e)}")
            raise Exception from e

    async def get_room(self, room_id: str, user_id: str) -> Optional[dict]:
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
                        Room.owner_id == user_id
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
                        "summaries": [],
                    }

                # fetch last 3 summaries in chronological order for join_room context
                summaries_result = await session.execute(
                    select(RoomSummaries)
                    .where(RoomSummaries.room_id == room_id)
                    .order_by(RoomSummaries.created_at.desc())
                    .limit(3)
                )
                summaries = list(reversed(summaries_result.scalars().all()))

                return {
                    "members": room.get_members(active_only=True),
                    "activities": room.get_activities(),
                    "room": room.to_dict(),
                    "summaries": [s.to_dict() for s in summaries],
                }

        except Exception as e:
            logger.error(f"Failed to get room: {str(e)}")
            raise Exception from e

    async def list_rooms(self, user_id: str) -> list[dict]:
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
        try:
            async with self.db.session() as session:
                result = await session.execute(
                    select(RoomMember)
                    .where(RoomMember.room_id == room_id, RoomMember.user_id == user_id)
                    .order_by(RoomMember.created_at.desc())
                )
                room_member = result.scalars().first()

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

    async def exit_room(self, room_id: str, user_id: str) -> bool:
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
