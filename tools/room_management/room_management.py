import os
import uuid
from fastmcp import Context
from config.logger import get_logger
from pathlib import Path
from datetime import datetime
import json

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