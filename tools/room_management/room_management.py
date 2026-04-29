import os
from typing import Optional
from fastmcp import Context
from config.logger import get_logger
from pathlib import Path
from datetime import datetime
import json

from handlers.room import RoomHanler
from models.rooms import RoomActivityTypes
from tools.room_management.utils import decode_invite_token, sign_invite_token

logger = get_logger(__name__)

class RoomManagement():
    def __init__(self, ctx: Context):
        """Bind request context, current user identity, and room handler access."""
        self.ctx = ctx
        self.user_id = os.getenv("BACKROOMS_USER_ID")
        if not self.user_id:
            raise ValueError("BACKROOMS_USER_ID is not set in environment.")
        
        self.db = self.ctx.lifespan_context.get("db")
        if not self.db:
            raise ValueError("FAILED: db is None — lifespan context not populated")
        
        self.room_handler = RoomHanler(self.db)

    def _get_invite_secret(self) -> str:
        """Load the signing secret only when invite flows actually need it."""
        invite_secret = os.getenv("BACKROOMS_INVITE_SECRET")
        if not invite_secret:
            raise ValueError("BACKROOMS_INVITE_SECRET is not set in environment.")
        return invite_secret

    def _config_path(self) -> Path:
        """Return the `.backroom.json` path for the current working directory."""
        return Path.cwd() / ".backroom.json"

    def _read_config(self) -> dict:
        """Read the local room config file for the current directory."""
        return json.loads(self._config_path().read_text())

    def _write_config(self, config_data: dict) -> None:
        """Persist room config back to `.backroom.json`."""
        self._config_path().write_text(json.dumps(config_data, indent=4))

    async def _resolve_join_target(
        self,
        room_id: Optional[str],
        token: Optional[str],
        config_data: dict,
        config_exists: bool,
    ) -> tuple[Optional[str], Optional[dict], Optional[str]]:
        """Resolve the requested join target from token, explicit room_id, or local config."""
        if room_id and token:
            return None, None, "FAILED: provide either room_id or token, not both"

        if token:
            return await self._resolve_join_from_token(token)

        if not room_id:
            if not config_exists:
                return None, None, "FAILED: .backroom.json not found"
            room_id = config_data.get("id")
            if not room_id:
                return None, None, "FAILED: room_id not found in .backroom.json"

        room_data = await self.room_handler.get_room(room_id, self.user_id)
        if not room_data or not room_data.get("room"):
            return None, None, "FAILED: room not found for this user"

        return room_id, room_data, None

    async def _resolve_join_from_token(
        self, token: str
    ) -> tuple[Optional[str], Optional[dict], Optional[str]]:
        """Validate an invite token and load the corresponding room metadata."""
        try:
            invite_payload = decode_invite_token(self._get_invite_secret(), token)
        except ValueError as exc:
            if str(exc) == "expired":
                return None, None, "FAILED: invite token expired"
            return None, None, "FAILED: invite token invalid"

        room_id = invite_payload["room_id"]
        room_data = await self.room_handler.get_room_by_id(room_id)
        if not room_data or not room_data.get("room"):
            return None, None, "FAILED: room not found"

        if invite_payload["version"] != room_data.get("room").get("invite_version"):
            return None, None, "FAILED: invite token invalid"

        return room_id, room_data, None

    def _update_local_config(self, config_data: dict, room_id: str, room_data: dict) -> None:
        """Refresh local room config after a successful join."""
        room = room_data.get("room", {})
        config_data["id"] = room_id
        config_data["name"] = room.get("name")
        config_data["owner_id"] = room.get("owner_id")
        config_data.setdefault("created_at", datetime.now().isoformat())
        self._write_config(config_data)

    def _join_activity_type(self, token: Optional[str]) -> str:
        """Choose the activity type for normal joins vs invite-based joins."""
        if token:
            return RoomActivityTypes.INVITE_ACCEPTED.value
        return RoomActivityTypes.MEMBER_JOINED.value

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
            config_path = self._config_path()
            config_data = {}
            config_exists = config_path.exists()
            if config_exists:
                config_data = self._read_config()

            room_id, room_data, error = await self._resolve_join_target(room_id=room_id, token=token, config_data=config_data, config_exists=config_exists)
            if error:
                return error

            # upsert into room_members with user_id, room_id, joined_at
            joined = await self.room_handler.join_room(room_id, self.user_id)
            if not joined:
                return "FAILED: failed to join room"

            # overwrite .backroom.json with the new room_id + name
            self._update_local_config(config_data, room_id, room_data)

            # log member_joined to room_activity
            activity_log = f"[MEMBER JOINED]-> user_id: {self.user_id} joined room_id: {room_id}"
            await self.room_handler.log_room_activity(
                room_id,
                self.user_id,
                self._join_activity_type(token),
                activity_log,
            )

            logger.info(f"Joined room '{room_data.get('room').get('name')}'.")
            return f"Joined room '{room_data.get('room').get('name')}'."
        except Exception as e:
            logger.error(f"Error joining room: {str(e)}")
            return f"FAILED to join room: {str(e)}"

    async def generate_invite(self, room_id: str) -> str:
        """Rotate the room invite version and return a fresh signed invite token."""
        try:
            room_data = await self.room_handler.bump_invite_version(room_id, self.user_id)
            if not room_data:
                return "FAILED: only the room owner can generate invites"

            token = sign_invite_token(
                secret=self._get_invite_secret(),
                room_id=str(room_data.get("id")),
                version=room_data.get("invite_version"),
            )
            activity_log = (
                f"[INVITE GENERATED]-> user_id: {self.user_id} generated invite "
                f"for room_id: {room_id} version: {room_data.get('invite_version')}"
            )
            await self.room_handler.log_room_activity(
                room_id,
                self.user_id,
                RoomActivityTypes.INVITE_CREATED.value,
                activity_log,
            )
            return token
        except Exception as e:
            logger.error(f"Error generating invite: {str(e)}")
            return f"FAILED to generate invite: {str(e)}"

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
            return []
