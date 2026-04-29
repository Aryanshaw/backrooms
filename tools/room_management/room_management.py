import os
import uuid
from fastmcp import Context
from config.logger import get_logger
from pathlib import Path
from datetime import datetime
import json
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from handlers.room import RoomHanler

logger = get_logger(__name__)

class RoomManagement():
    def __init__(self, ctx: Context):
        self.ctx = ctx
        self.user_id = os.getenv("BACKROOMS_USER_ID")
        if not self.user_id:
            raise ValueError("BACKROOMS_USER_ID is not set in environment.")
        
        self.db = self.ctx.lifespan_context.get("db")
        if not self.db:
            raise ValueError("FAILED: db is None — lifespan context not populated")
        
        self.room_handler = RoomHanler(self.ctx.lifespan_context.get("db"))

    async def init_room(self, name: str) -> str:
        """
        - Check if .backroom.json already exists in cwd — if yes, return early with "already initialized"
        - Check if a room with that name already exists in DB for this user — if yes, error
        - Insert new row into rooms table
        - Write .backroom.json to cwd with room_name, owner_id, created_at
        - Return confirmation with room name
        """
        try:
            config_path = Path.cwd() / ".backroom.json"
            if config_path.exists():
                return "FAILED: .backroom.json already exists"

            # create room in database
            room_data = await self.room_handler.create_room(name , self.user_id)
            
            config_data = {
                "id": str(room_data.get("room_id")),
                "name": name,
                "owner_id": self.user_id,
                "created_at": datetime.now().isoformat(),
            }
            config_path.write_text(json.dumps(config_data, indent=4))

            logger.info(f"Room '{name}' initialized.")
            return f"Room '{name}' initialized."
        except Exception as e:
            logger.error(f"Error initializing room: {str(e)}")
            return f"FAILED to initialize room: {str(e)}"
        
    async def list_rooms(self) -> list:
        """
        - Get the current user's ID 
        - Query the database for all rooms owned by this user
        - Return room details with last_active and active tool list
        - Order by last_active desc
        """
        try:
            db = self.ctx.lifespan_context.get("db")
            if db is None:
                logger.error("DB is None — lifespan context not populated")
                return []
            async with db.session() as session:
                result = await session.execute(
                    select(Room)
                    .options(selectinload(Room.members))
                    .where(Room.owner_id == self.user_id)
                    .order_by(Room.last_active.desc())
                )
                rooms = result.scalars().all()
                room_summaries = [
                    {
                        "id": str(room.id),
                        "name": room.name,
                        "owner_id": room.owner_id,
                        "created_at": room.created_at.isoformat(),
                        "last_active": room.last_active.isoformat(),
                        "active_tools": sorted({member.tool for member in room.members}),
                    }
                    for room in rooms
                ]
                logger.info(f"Retrieved rooms for user {self.user_id}: {rooms}")
                return room_summaries
        except Exception as e:
            logger.error(f"Error listing rooms: {str(e)}")
            return []
        
    async def switch_room(self, name: str) -> str:
        """
        - Check if .backroom.json exists in cwd — if not, error "not initialized"
        - Check if a room with that name exists in DB for this user — if not, error
        - Update .backroom.json with new room_name, owner_id, created_at
        - Return confirmation with new room name
        """
        try:
            config_path = Path.cwd() / ".backroom.json"
            if not config_path.exists():
                return "FAILED: .backroom.json does not exist — not initialized"

            db = self.ctx.lifespan_context.get("db")
            if db is None:
                return "FAILED: db is None — lifespan context not populated"

            async with db.session() as session:
                result = await session.execute(
                    select(Room.id, Room.created_at).where(
                        Room.name == name,
                        Room.owner_id == self.user_id,
                    )
                )
                row = result.first()
                if row is None:
                    return f"FAILED: No room named '{name}' found for this user."
                room_id, created_at = row

            config_data = {
                "id": str(room_id),
                "name": name,
                "owner_id": self.user_id,
                "created_at": created_at.isoformat(),
            }
            config_path.write_text(json.dumps(config_data, indent=4))
            
            logger.info(f"Switched to room '{name}'.")
            return f"Switched to room '{name}'."
        except Exception as e:
            logger.error(f"Error switching rooms: {str(e)}")
            return f"FAILED to switch rooms: {str(e)}"
