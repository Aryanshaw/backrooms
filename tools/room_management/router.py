# tools/room_management.py
from typing import Optional
from fastmcp import FastMCP, Context
from config.logger import get_logger
from sqlalchemy import text

from tools.room_management.room_management import RoomManagement

logger = get_logger(__name__)

room_management_router = FastMCP("room-management")

@room_management_router.tool()
async def init_room(name: str, ctx: Context) -> str:
    """
    ALWAYS call this to create a NEW Backrooms room in the current directory.
    Creates a .backroom.json file and registers the room in the database.
    Use this ONLY when starting a fresh project that has no room yet.
    Do NOT call this if .backroom.json already exists — call join_room instead.

    INPUT:
    - name (str): name of the room to initialize

    OUPUT:
    text response denoting the success/failure status

    """
    room_management = RoomManagement(ctx)
    return await room_management.init_room(name)

@room_management_router.tool()
async def join_room(room_id: Optional[str] = None, ctx: Context = None) -> str:
    """
    ALWAYS call this at the start of every session if .backroom.json exists in cwd.
    Joins this agent to the specified room and updates .backroom.json.
    
    This is how Backrooms shares context across AI tools — Claude Code, Cursor, OpenCode.
    Each tool calls join_room at session start so all agents are aware of each other.

    INPUT:
    - room_id (Optional[str]): room_id to join
        - if not provided, the tool will read .backroom.json from cwd and get the room_id and join the room with the room_id in the .backroom.json
        - if provided, the tool will let the agent join the room with the provided room_id

    OUPUT:
    text response denoting the success/failure status
    """
    room_management = RoomManagement(ctx)
    return await room_management.join_room(room_id)

@room_management_router.tool()
async def get_current_room(room_id: Optional[str] = None, ctx: Context = None) -> str:
    """
    Call this to check which room is currently active in this directory.
    Returns room name and summary.

    INPUT:
    - room_id (Optional[str]): room_id to get the info for
        - if not provided, read .backroom.json from cwd and get the room_id
        - if provided, use the provided room_id

    OUPUT:
    text response denoting the room name, number of members and last_active

    Example:
    "Room 'my-room' with 2 members and last_active: 2026-04-29T16:53:22.203471"
    """
    room_management = RoomManagement(ctx)
    return await room_management.get_room_info(room_id)

@room_management_router.tool()
async def list_rooms(ctx: Context) -> str:
    """
    Call this to get a list of all available Backrooms owned by the
    authenticated user on the server.

    INPUT:
    - ctx (Context): FastMCP request context

    OUTPUT:
    text response containing the list of room names ordered by activity
    """
    room_management = RoomManagement(ctx)
    return await room_management.list_rooms()


@room_management_router.tool()
async def setup_agents_md(ctx: Context) -> str:
    """
    ALWAYS call this to configure AGENTS.md for Backrooms in the current directory.
    This is ONLY about the AGENTS.md file — it has nothing to do with creating or joining rooms.
    Call this after init_room to ensure all AI tools automatically join the room at session start.
    
    Also call this anytime AGENTS.md is missing or the Backrooms section is outdated.
    """
    room_management = RoomManagement(ctx)
    return await room_management.setup_agents_md()

@room_management_router.tool()
async def test_db_connection(ctx: Context) -> str:
    """Test if DB connection is accessible from mounted router."""
    try:
        logger.info("Testing DB connection from mounted router.")
        db = ctx.lifespan_context.get("db")
        if db is None:
            return "FAILED: db is None — lifespan context not populated"
        async with db.session() as session:
            result = await session.execute(text("SELECT 1"))
            value = result.scalar()
            logger.info(f"DB accessible from router. Result: {value}")

        return f"DB accessible from router. Result: {value}"
    except Exception as e:
        logger.error(f"Error testing DB connection from mounted router: {str(e)}")
        return f"FAILED: {str(e)}"
