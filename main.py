"""Standalone FastAPI REST server for lightweight status queries.

Runs on port 80 alongside the FastMCP server (port 8000).
Used by hooks and statusline integrations that need room metadata
without going through the full MCP protocol.
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import func, select

from config.db import connect_db
from config.logger import get_logger
from models.message import RoomSummaries
from models.rooms import Room

logger = get_logger(__name__)

_db = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _db
    async with connect_db() as db:
        _db = db
        logger.info("REST API startup complete.")
        yield
    _db = None
    logger.info("REST API shutdown complete.")


app = FastAPI(lifespan=lifespan)


@app.get("/room-status")
async def room_status(room_id: str = Query(..., description="Room UUID")):
    """
    Returns room name and summary count for a given room_id.
    Used by the backrooms-plugin statusline hook.
    No auth — room_id acts as the shared secret.
    """
    if not _db:
        raise HTTPException(status_code=503, detail="Database not ready")

    async with _db.session() as session:
        room_result = await session.execute(
            select(Room.name).where(Room.id == room_id)
        )
        room_name = room_result.scalar_one_or_none()
        if not room_name:
            raise HTTPException(status_code=404, detail="Room not found")

        count_result = await session.execute(
            select(func.count()).select_from(RoomSummaries).where(
                RoomSummaries.room_id == room_id
            )
        )
        summary_count = count_result.scalar()

    return {"room_name": room_name, "summary_count": summary_count}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=80, reload=True)
