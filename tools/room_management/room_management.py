import os
from typing import Optional
from fastmcp import Context
from config.logger import get_logger
from pathlib import Path
from datetime import datetime
import json

from handlers.room import RoomHanler
from models.rooms import RoomActivityTypes
from prompt import BACKROOMS_MARKER_START , BACKROOMS_MARKER_END , BACKROOMS_SECTION


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
        
        self.room_handler = RoomHanler(self.db)

    async def init_room(self, name: str) -> str:
        """
        - Check if .backroom.json already exists in cwd — if yes, return early with "already initialized"
        - Check if a room with that name already exists in DB for this user — if yes, error
        - Insert new row into rooms table
        - Write .backroom.json to cwd with room_name, owner_id, created_at
        - Join the room
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

            # join the room
            joined = await self.join_room(str(room_data.get("room_id")))
            if not joined:
                return "FAILED: failed to join room after initializing"

            logger.info(f"Room '{name}' initialized and joined.")
            return f"Room '{name}' initialized and joined."
        except Exception as e:
            logger.error(f"Error initializing room: {str(e)} after joining")
            return f"FAILED to initialize room: {str(e)} after joining"
    
    async def join_room(self, room_id: Optional[str] = None) -> str:
        """
        - Accept room_id as parameter
        - Query DB — if room doesn't exist, return error
        - Upsert into room_members with user_id, room_id, joined_at
        - Update last_active on the room row
        - Overwrite .backroom.json with the new room_id + name
        - Log member_joined to room_activity
        - Return room name + confirmation
        """
        try:
            # check if .backroom.json exists
            config_path = Path.cwd() / ".backroom.json"
            if not config_path.exists():
                return "FAILED: .backroom.json not found"

            # load the .backroom.json file
            config_data = json.loads(config_path.read_text())

            # get the room_id from the .backroom.json file
            room_id = config_data.get("id")
            if not room_id:
                return "FAILED: room_id not found in .backroom.json"

            # check if the room exists in the database for the user
            room_data = await self.room_handler.get_room(room_id, self.user_id)
            if not room_data or not room_data.get("room"):
                return "FAILED: room not found for this user"

            # upsert into room_members with user_id, room_id, joined_at
            joined = await self.room_handler.join_room(room_id, self.user_id)
            if not joined:
                return "FAILED: failed to join room"

            # overwrite .backroom.json with the new room_id + name
            config_data["id"] = room_id
            config_path.write_text(json.dumps(config_data, indent=4))

            # log member_joined to room_activity
            activity_log = f"[MEMBER JOINED]-> user_id: {self.user_id} joined room_id: {room_id}"
            await self.room_handler.log_room_activity(room_id, self.user_id, str(RoomActivityTypes.MEMBER_JOINED), activity_log)

            logger.info(f"Joined room '{room_data.get('room').get('name')}'.")
            return f"Joined room '{room_data.get('room').get('name')}'."
        except Exception as e:
            logger.error(f"Error joining room: {str(e)}")
            return f"FAILED to join room: {str(e)}"

    async def get_room_info(self, room_id: Optional[str] = None) -> str:
        """
        - Accept room_id as optional parameter
        - If room_id is not provided, read .backroom.json from cwd — if not found, return error "no room found, call init_room first"
        - If room_id is provided, query DB — if room doesn't exist, return error
        - Return room name + list of current members + last_active
        """
        try:
            # if room_id is not provided, read .backroom.json from cwd and get the room_id
            if not room_id:
                config_path = Path.cwd() / ".backroom.json"
                if not config_path.exists():
                    return "FAILED: .backroom.json not found"

                config_data = json.loads(config_path.read_text())
                room_id = config_data.get("id")
                if not room_id:
                    return "FAILED: room_id not found in .backroom.json"

            # query the room from the database
            room_data = await self.room_handler.get_room(room_id, self.user_id)
            if not room_data.get("room"):
                return "FAILED: room not found for this user"

            # return the room name + list of current members + last_active
            return f"Room '{room_data.get('room').get('name')}' with {len(room_data.get('members'))} members and last_active: {str(room_data.get('room').get('last_active'))}"
        except Exception as e:
            logger.error(f"Error getting room info: {str(e)}")
            return f"FAILED to get room info: {str(e)}"
        
    async def list_rooms(self) -> str:
        """
        - Get the current user's ID 
        - Query the database for all rooms owned by this user
        - Return room details with last_active and active tool list
        - Order by last_active desc
        """
        try:
            rooms = await self.room_handler.list_rooms(self.user_id)
            logger.info(f"Retrieved rooms for user {self.user_id}: {rooms}")
            return json.dumps(rooms, indent=4)
        except Exception as e:
            logger.error(f"Error listing rooms: {str(e)}")
            return f"FAILED to list rooms: {str(e)}"
        
    async def setup_agents_md(self) -> str:
        """
        Create or update AGENTS.md with Backrooms instructions.
        Uses markers to safely update only the Backrooms section without touching existing content.
        """
        try:
            agents_md_path = Path.cwd() / "AGENTS.md"

            if not agents_md_path.exists():
                agents_md_path.write_text(BACKROOMS_SECTION)
                return "AGENTS.md created with Backrooms section."

            content = agents_md_path.read_text()

            if BACKROOMS_MARKER_START in content and BACKROOMS_MARKER_END in content:
                # replace only the backrooms section
                before = content[:content.index(BACKROOMS_MARKER_START)]
                after = content[content.index(BACKROOMS_MARKER_END) + len(BACKROOMS_MARKER_END):]
                agents_md_path.write_text(before + BACKROOMS_SECTION + after)
                return "AGENTS.md Backrooms section updated."

            # append if markers not found
            agents_md_path.write_text(content.rstrip() + "\n\n" + BACKROOMS_SECTION)
            return "Backrooms section appended to existing AGENTS.md."

        except Exception as e:
            logger.error(f"Error setting up AGENTS.md: {str(e)}")
            return f"FAILED to setup AGENTS.md: {str(e)}"