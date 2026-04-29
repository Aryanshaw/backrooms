# tools/messaging/router.py
from fastmcp import FastMCP, Context
from config.logger import get_logger

from tools.messaging.message import Messaging

logger = get_logger(__name__)

messaging_router = FastMCP("messaging")


@messaging_router.tool()
async def push_message(user_content: str, assistant_content: str, ctx: Context) -> str:
    """
    ALWAYS call this after EVERY assistant response to persist the conversation turn.
    Pushes the user message and assistant response as a pair to the active room.
    Room is resolved automatically from .backroom.json in cwd — no room_id needed.

    INPUT:
    - user_content (str): the user's message text
    - assistant_content (str): the assistant's response text

    OUTPUT (normal):
        '{"status": "ok"}'

    OUTPUT (summary threshold exceeded):
        '{
            "status": "summary_needed",
            "last_summarized_message_id": "<uuid or null>",
            "unsummarized_message_count": <int>
        }'

    NEVER call this if .backroom.json does not exist — call join_room first.
    NEVER call this with empty user_content or assistant_content.
    """
    messaging = Messaging(ctx)
    return await messaging.push_message(user_content, assistant_content)
