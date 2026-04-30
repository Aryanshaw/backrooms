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
    Backrooms gives AI tools persistent, cross-session memory via rooms. With this claude code / codex / cursor agents will be able to share context across sessions.
    Each project directory anchors to a room via .backroom.json.

    ## Tools
    Room Management Tools:
        - init_room(name) — create a new room for this directory
        - join_room(room_id: Optional) — join or switch to a room  
        - get_current_room(room_id: Optional) — check active room and members
        - list_rooms() — see all your rooms
        - exit_room() — leave the current room

    ## Rules
    - If .backroom.json exists in cwd, ALWAYS call join_room at session start
    - If starting a fresh project, call init_room first
    - Call get_current_room to confirm context before starting work
    """


app = create_streamable_http_app(
    server=mcp,
    streamable_http_path="/mcp/",
    debug=True,
)

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
