"""FastMCP server with streamable HTTP transport."""

from contextlib import asynccontextmanager

import uvicorn
from fastmcp import FastMCP
from fastmcp.server.http import create_streamable_http_app

from config.db import connect_db
from config.logger import get_logger
from tools.room_management.router import room_management_router
from tools.messaging.router import messaging_router


logger = get_logger(__name__)


@asynccontextmanager
async def app_lifespan(app):
    logger.info("Application startup initiated.")
    async with connect_db() as db:
        logger.info("Application startup completed.")
        yield {"db": db}
    logger.info("Application shutdown completed.")


mcp = FastMCP("MyServer", lifespan=app_lifespan)
mcp.mount(room_management_router)
mcp.mount(messaging_router)

@mcp.prompt()
def backrooms_guide() -> str:
    """Overview of Backrooms MCP server and how to use it."""
    return """
    # Backrooms — Shared Memory Layer for AI Tools

    ## What it is
    Backrooms gives AI tools persistent, cross-session memory via rooms.
    Agents across Claude Code, Cursor, Codex share context via summaries stored per room.
    Each project directory anchors to a room via .backroom.json.

    ## Session Start
    1. If .backroom.json exists — call join_room immediately (returns last 3 summaries)
    2. If not — call list_rooms, then init_room(name) or join_room(room_id)
    3. Call get_current_room to confirm active room

    ## During Session
    - Call submit_summary(content) when context is long, at session end, or before switching tools
    - Call pull_summaries() if you need more history than join_room returned

    ## Tools
    Room Management:
        - init_room(name) — create new room, writes .backroom.json
        - join_room(room_id?) — join room, returns last 3 summaries
        - get_current_room(room_id?) — check active room and members
        - list_rooms() — see all your rooms
        - exit_room() — leave current room
        - setup_agents_md() — write AGENTS.md and CLAUDE.md with Backrooms rules

    Summaries:
        - submit_summary(content) — persist session summary to room
        - pull_summaries(limit, offset) — fetch past summaries with pagination
    """


app = create_streamable_http_app(
    server=mcp,
    streamable_http_path="/mcp/",
    debug=True,
)

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
