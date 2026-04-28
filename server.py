"""FastMCP server with streamable HTTP transport."""

from contextlib import asynccontextmanager

import uvicorn
from fastmcp import Context, FastMCP
from fastmcp.server.http import create_streamable_http_app

from config.db import connect_db
from config.logger import get_logger
from tools.room_management.router import room_management_router as room_management_router


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


app = create_streamable_http_app(
    server=mcp,
    streamable_http_path="/mcp/",
    debug=True,
)

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
