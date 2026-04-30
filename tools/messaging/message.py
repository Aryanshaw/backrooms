import json
from typing import Optional
from fastmcp import Context
from config.logger import get_logger

from handlers.message import MessageHandler
from tools.base import BackroomsBase

logger = get_logger(__name__)


class Messaging(BackroomsBase):
    def __init__(self, ctx: Context):
        super().__init__(ctx)
        self.message_handler = MessageHandler(self.db)

    async def push_message(self, user_content: str, assistant_content: str) -> str:
        try:
            config_path = self._config_path()
            if not config_path.exists():
                return "FAILED: .backroom.json not found — call join_room first"

            config_data = self._read_config()
            room_id = config_data.get("id")
            if not room_id:
                return "FAILED: room_id not found in .backroom.json"

            result = await self.message_handler.push_message(
                room_id=room_id,
                user_id=self.user_id,
                user_content=user_content,
                assistant_content=assistant_content,
            )

            logger.info(f"push_message result for room {room_id}: {result}")
            return json.dumps(result)

        except Exception as e:
            logger.error(f"Error in push_message: {str(e)}")
            return f"FAILED to push message: {str(e)}"

    async def pull_messages(self, limit: int = 20, offset: int = 0, after_id: Optional[str] = None) -> str:
        try:
            config_path = self._config_path()
            if not config_path.exists():
                return "FAILED: .backroom.json not found — call join_room first"

            config_data = self._read_config()
            room_id = config_data.get("id")
            if not room_id:
                return "FAILED: room_id not found in .backroom.json"

            result = await self.message_handler.pull_messages(
                room_id=room_id,
                limit=limit,
                offset=offset,
                after_id=after_id,
            )

            logger.info(f"pull_messages result for room {room_id}: {result['total_messages']} total")
            return json.dumps(result, default=str)

        except Exception as e:
            logger.error(f"Error in pull_messages: {str(e)}")
            return f"FAILED to pull messages: {str(e)}"

    async def submit_summary(self, content: str, from_message_id: str, to_message_id: str) -> str:
        try:
            config_path = self._config_path()
            if not config_path.exists():
                return "FAILED: .backroom.json not found — call join_room first"

            config_data = self._read_config()
            room_id = config_data.get("id")
            if not room_id:
                return "FAILED: room_id not found in .backroom.json"

            result = await self.message_handler.submit_summary(
                room_id=room_id,
                user_id=self.user_id,
                content=content,
                from_message_id=from_message_id,
                to_message_id=to_message_id,
            )

            logger.info(f"submit_summary result for room {room_id}: {result}")
            return json.dumps(result)

        except Exception as e:
            logger.error(f"Error in submit_summary: {str(e)}")
            return f"FAILED to submit summary: {str(e)}"
