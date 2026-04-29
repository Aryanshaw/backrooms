import uuid
from config.logger import get_logger
from models.rooms import Room, RoomActivity, RoomActivityTypes

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
