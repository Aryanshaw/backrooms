import uuid
from config.logger import get_logger
from models.rooms import Room, RoomActivity, RoomActivityTypes
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
            async with self.db.session() as session:
                # create a new room
                room = Room(id=room_id, name=name, owner_id=user_id)
                session.add(room)

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

    async def list_rooms(self, user_id: str):
        try:
            async with self.db.session() as session:
                result = await session.execute(
                    select(Room)
                    .options(selectinload(Room.members))
                    .where(Room.owner_id == user_id)
                    .order_by(Room.last_active.desc())
                )
                rooms = result.scalars().all()

            return [
                {
                    "id": str(room.id),
                    "name": room.name,
                    "owner_id": room.owner_id,
                    "created_at": room.created_at.isoformat(),
                    "last_active": room.last_active.isoformat(),
                    "active_tools": sorted(
                        {
                            member_tool
                            for member in room.members
                            for member_tool in [getattr(member, "tool", None)]
                            if member_tool
                        }
                    ),
                }
                for room in rooms
            ]
        except Exception as e:
            logger.error(f"Failed to list rooms: {str(e)}")
            raise Exception from e

    async def get_room_by_name_for_user(self, name: str, user_id: str):
        try:
            async with self.db.session() as session:
                result = await session.execute(
                    select(Room.id, Room.created_at).where(
                        Room.name == name,
                        Room.owner_id == user_id,
                    )
                )
                row = result.first()

            if row is None:
                return None

            room_id, created_at = row
            return {
                "id": str(room_id),
                "created_at": created_at.isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to fetch room for switch: {str(e)}")
            raise Exception from e
