# tools/messaging/router.py
from fastmcp import FastMCP, Context
from config.logger import get_logger

from tools.messaging.message import Messaging

logger = get_logger(__name__)

messaging_router = FastMCP("messaging")


@messaging_router.tool()
async def submit_summary(content: str, ctx: Context) -> str:
    """
    ALWAYS call this to persist a session summary to the active room.
    Call this when context is getting long, at end of session, or when switching tools.
    Room is resolved automatically from .backroom.json in cwd.

    INPUT:
    - content (str): the summary text — follow the format below strictly

    OUTPUT (success): '{"status": "ok"}'
    OUTPUT (validation fail): '{"status": "error", "message": "FAILED: ..."}'

    ───────────────────────────────────────────
    SUMMARY FORMAT (strict — follow exactly)
    ───────────────────────────────────────────

    ## Problem Statement
    What problem or goal was being worked on. One short paragraph.
    Be specific — not "we worked on the app" but "we were trying to fix the
    auth token expiry bug that caused users to be logged out mid-session."

    ## What Was Tried (including failures)
    List of approaches attempted, including ones that failed and why.
    Failures are critical context — do not omit them.
    Format: "Tried X → result / why it failed"

    ## Decisions Made
    List of final decisions reached, with reasoning.
    Format: "Decided X because Y"

    ## Current State
    Where things stand — what is done, in progress, blocked.
    Be precise about stopping point so next agent can resume without asking.

    ## Open Questions
    Unresolved questions or deferred decisions.

    ## Key References
    File names, function names, endpoints essential for whoever picks this up next.

    ───────────────────────────────────────────

    NEVER skip sections — write "None" if nothing applies.
    NEVER summarize vaguely — a future agent must resume from this summary alone.
    NEVER call this if .backroom.json does not exist — call join_room first.
    """
    messaging = Messaging(ctx)
    return await messaging.submit_summary(content)


@messaging_router.tool()
async def pull_summaries(ctx: Context, limit: int = 10, offset: int = 0) -> str:
    """
    Call this to fetch past summaries from the active room.
    Returns summaries in chronological order.
    Room is resolved automatically from .backroom.json in cwd.

    INPUT:
    - limit (int, default 10): number of summaries to return
    - offset (int, default 0): number of summaries to skip (for pagination)

    OUTPUT:
    '{
        "summaries": [{ "id": str, "summary": str, "created_at": str }],
        "total": int,
        "has_more": bool
    }'

    NEVER call this if .backroom.json does not exist — call join_room first.
    """
    messaging = Messaging(ctx)
    return await messaging.pull_summaries(limit=limit, offset=offset)
