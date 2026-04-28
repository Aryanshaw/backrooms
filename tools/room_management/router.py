# tools/room_management.py
from fastmcp import FastMCP, Context
from config.logger import get_logger
from sqlalchemy import text

logger = get_logger(__name__)

room_management_router = FastMCP("room-management")

@room_management_router.tool()
async def init_room(name: str, ctx: Context) -> str:
    """
    ALWAYS call this to initialize a new MemRoom in the current directory.
    Creates a .memroom.json file and registers the room on the server.
    """
    db = ctx.lifespan_context.get("db")
    if db is None:
        return "FAILED: db is None — lifespan context not populated"
    # your logic here
    return f"Room '{name}' initialized."

@room_management_router.tool()
async def join_room(ctx: Context) -> str:
    """
    ALWAYS call this at the start of every session if .memroom.json exists.
    Reads the local .memroom.json and registers this agent as an active member.
    """
    # your logic here
    return "Joined room."

@room_management_router.tool()
async def get_current_room(ctx: Context) -> str:
    """
    Call this to check which room is currently active in this directory.
    Returns room name and summary.
    """
    # your logic here
    return "Current room: ..."

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
