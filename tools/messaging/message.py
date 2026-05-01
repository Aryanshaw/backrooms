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

    async def submit_summary(self, content: str) -> str:
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
            )

            logger.info(f"submit_summary result for room {room_id}: {result}")
            return json.dumps(result)

        except Exception as e:
            logger.error(f"Error in submit_summary: {str(e)}")
            return f"FAILED to submit summary: {str(e)}"

    async def pull_summaries(self, page: int = 1) -> str:
        try:
            config_path = self._config_path()
            if not config_path.exists():
                return "FAILED: .backroom.json not found — call join_room first"

            config_data = self._read_config()
            room_id = config_data.get("id")
            if not room_id:
                return "FAILED: room_id not found in .backroom.json"

            page = max(1, page)
            limit = 20
            offset = (page - 1) * limit

            result = await self.message_handler.pull_summaries(
                room_id=room_id,
                limit=limit,
                offset=offset,
            )
            result["page"] = page

            logger.info(f"pull_summaries result for room {room_id}: {result['total']} total")
            return json.dumps(result, default=str)

        except Exception as e:
            logger.error(f"Error in pull_summaries: {str(e)}")
            return f"FAILED to pull summaries: {str(e)}"
