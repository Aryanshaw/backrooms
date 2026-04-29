import json
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
