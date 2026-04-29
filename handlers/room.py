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

    async def list_rooms(self, user_id: str) -> list[dict]:
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
        try:
            async with self.db.session() as session:
                room_member = RoomMember(id=str(uuid.uuid4()), room_id=room_id, user_id=user_id, joined_at=datetime.now())
                session.add(room_member)
                await session.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to join room: {str(e)}")
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
