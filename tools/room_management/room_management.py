from typing import Optional
from fastmcp import Context
from config.logger import get_logger
from pathlib import Path
from datetime import datetime
import json
import os

from handlers.room import RoomHandler
from models.rooms import RoomActivityTypes
from tools.room_management.utils import decode_invite_token
from prompt import BACKROOMS_MARKER_START , BACKROOMS_MARKER_END , BACKROOMS_SECTION
from tools.base import BackroomsBase


logger = get_logger(__name__)


class RoomManagement(BackroomsBase):
    def __init__(self, ctx: Context):
        """Bind request context, current user identity, and room handler access."""
        super().__init__(ctx)
        self.room_handler = RoomHandler(self.db)

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
            config_path = self._config_path()
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
            self._write_config(config_data)

            # join the room
            joined_message = await self.join_room(str(room_data.get("room_id")))
            if joined_message.startswith("FAILED"):
                return "FAILED: failed to join room after initializing"
            
            # setup AGENTS.md and CLAUDE.md
            await self.setup_agents_md()

            logger.info(f"Room '{name}' initialized and joined.")
            return f"Room '{name}' initialized and joined."
        except Exception as e:
            logger.error(f"Error initializing room: {str(e)} after joining")
            return f"FAILED to initialize room: {str(e)} after joining"
    
    async def join_room(self, room_id: Optional[str] = None, token: Optional[str] = None) -> str:
        """
        - Accept room_id or invite token as parameter
        - Query DB — if room doesn't exist, return error
        - Upsert into room_members with user_id, room_id, joined_at
        - Update last_active on the room row
        - Overwrite .backroom.json with the new room_id + name
        - Log member_joined to room_activity
        - Return room name + confirmation
        """
        try:
            if room_id and token:
                return "FAILED: provide either room_id or token, not both"

            config_path = self._config_path()
            config_data = {}
            if config_path.exists():
                config_data = self._read_config()

            if token:
                invite_secret = os.getenv("BACKROOMS_INVITE_SECRET")
                if not invite_secret:
                    return "FAILED: BACKROOMS_INVITE_SECRET is not set in environment"
                try:
                    invite_payload = decode_invite_token(invite_secret, token)
                except ValueError as exc:
                    if str(exc) == "expired":
                        return "FAILED: invite token expired"
                    return "FAILED: invite token invalid"

                room_id = invite_payload["room_id"]
                room_data = await self.room_handler.get_room_by_id(room_id)
                if not room_data or not room_data.get("room"):
                    return "FAILED: room not found"
                if invite_payload["version"] != room_data.get("room").get("invite_version"):
                    return "FAILED: invite token invalid"
            elif not room_id:
                if not config_path.exists():
                    return "FAILED: .backroom.json not found"
                room_id = config_data.get("id")
                if not room_id:
                    return "FAILED: room_id not found in .backroom.json"
                room_data = await self.room_handler.get_room(room_id, self.user_id)
                if not room_data or not room_data.get("room"):
                    return "FAILED: room not found for this user"
            else:
                room_data = await self.room_handler.get_room(room_id, self.user_id)
                if not room_data or not room_data.get("room"):
                    return "FAILED: room not found for this user"

            # upsert into room_members with user_id, room_id, joined_at
            joined = await self.room_handler.join_room(room_id, self.user_id)
            if not joined:
                return "FAILED: failed to join room"

            # overwrite .backroom.json with the new room_id + name
            config_data["id"] = room_id
            config_data["name"] = room_data.get("room").get("name")
            config_data["owner_id"] = room_data.get("room").get("owner_id")
            config_data.setdefault("created_at", datetime.now().isoformat())
            self._write_config(config_data)

            activity_label = "INVITE ACCEPTED" if token else "MEMBER JOINED"
            activity_log = f"[{activity_label}]-> user_id: {self.user_id} joined room_id: {room_id}"
            await self.room_handler.log_room_activity(
                room_id,
                self.user_id,
                RoomActivityTypes.INVITE_ACCEPTED.value if token else RoomActivityTypes.MEMBER_JOINED.value,
                activity_log,
            )

            room_name = room_data.get("room").get("name")
            summary = room_data.get("summary")

            logger.info(f"Joined room '{room_name}'.")

            if summary:
                return f"Joined room '{room_name}'.\n\nLast summary:\n{summary}"
            else:
                return f"Joined room '{room_name}'. No summary yet — call pull_messages to load recent history."
        except Exception as e:
            logger.error(f"Error joining room: {str(e)}")
            return f"FAILED to join room: {str(e)}"

    async def exit_room(self) -> str:
        """Leave the current room and remove the local directory link."""
        try:
            config_path = self._config_path()
            if not config_path.exists():
                return "FAILED: .backroom.json not found"

            config_data = self._read_config()
            room_id = config_data.get("id")
            if not room_id:
                return "FAILED: room_id not found in .backroom.json"

            exited = await self.room_handler.exit_room(room_id, self.user_id)
            if not exited:
                return "FAILED: no active room membership found"

            activity_log = (
                f"[MEMBER LEFT]-> user_id: {self.user_id} left room_id: {room_id}"
            )
            await self.room_handler.log_room_activity(
                room_id,
                self.user_id,
                RoomActivityTypes.MEMBER_LEFT.value,
                activity_log,
            )

            room_name = config_data.get("name", room_id)
            config_path.unlink(missing_ok=True)
            logger.info(f"Exited room '{room_name}'.")
            return f"Exited room '{room_name}'."
        except Exception as e:
            logger.error(f"Error exiting room: {str(e)}")
            return f"FAILED to exit room: {str(e)}"

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
                config_path = self._config_path()
                if not config_path.exists():
                    return "FAILED: .backroom.json not found"

                config_data = self._read_config()
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
        Create or update AGENTS.md and CLAUDE.md with Backrooms instructions.
        Uses markers to safely update only the Backrooms section without touching existing content.
        """
        try:
            agents_md_path = Path.cwd() / "AGENTS.md"
            claude_md_path = Path.cwd() / "CLAUDE.md"

            if not claude_md_path.exists():
                claude_md_path.write_text(BACKROOMS_SECTION)
                return "CLAUDE.md created with Backrooms section."

            if not agents_md_path.exists():
                agents_md_path.write_text(BACKROOMS_SECTION)
                return "AGENTS.md created with Backrooms section."

            agents_content = agents_md_path.read_text()
            claude_content = claude_md_path.read_text()

            if BACKROOMS_MARKER_START in agents_content and BACKROOMS_MARKER_END in agents_content:
                # replace only the backrooms section
                before = agents_content[:agents_content.index(BACKROOMS_MARKER_START)]
                after = agents_content[agents_content.index(BACKROOMS_MARKER_END) + len(BACKROOMS_MARKER_END):]
                agents_md_path.write_text(before + BACKROOMS_SECTION + after)
                return "AGENTS.md Backrooms section updated."

            if BACKROOMS_MARKER_START in claude_content and BACKROOMS_MARKER_END in claude_content:
                # replace only the backrooms section
                before = claude_content[:claude_content.index(BACKROOMS_MARKER_START)]
                after = claude_content[claude_content.index(BACKROOMS_MARKER_END) + len(BACKROOMS_MARKER_END):]
                claude_md_path.write_text(before + BACKROOMS_SECTION + after)
                return "CLAUDE.md Backrooms section updated."

            # append if markers not found
            agents_md_path.write_text(agents_content.rstrip() + "\n\n" + BACKROOMS_SECTION)
            claude_md_path.write_text(claude_content.rstrip() + "\n\n" + BACKROOMS_SECTION)
            return "Backrooms section appended to existing AGENTS.md CLAUDE.md."

        except Exception as e:
            logger.error(f"Error setting up AGENTS.md and CLAUDE.md: {str(e)}")
            return f"FAILED to setup AGENTS.md and CLAUDE.md: {str(e)}"
