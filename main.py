"""FastAPI dashboard HTTP API."""

import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from config.db import connect_db
from config.logger import get_logger
from handlers.room import RoomHandler
from models.rooms import RoomActivityTypes
from tools.room_management.utils import sign_invite_token


logger = get_logger(__name__)


class GenerateInviteRequest(BaseModel):
    user_id: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FastAPI dashboard API startup initiated.")
    async with connect_db() as db:
        app.state.db = db
        logger.info("FastAPI dashboard API startup completed.")
        yield
    logger.info("FastAPI dashboard API shutdown completed.")


app = FastAPI(title="Backrooms Dashboard API", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/rooms/{room_id}/invites")
async def generate_invite(
    room_id: str,
    request: Request,
    payload: Optional[GenerateInviteRequest] = None,
    x_backrooms_user_id: Optional[str] = Header(default=None),
) -> dict:
    user_id = (payload.user_id if payload else None) or x_backrooms_user_id or os.getenv("BACKROOMS_USER_ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user id.")

    room_handler = RoomHandler(request.app.state.db)
    room_data = await room_handler.bump_invite_version(room_id, user_id)
    if not room_data:
        raise HTTPException(
            status_code=403,
            detail="Only the room owner can generate invites.",
        )

    invite_secret = os.getenv("BACKROOMS_INVITE_SECRET")
    if not invite_secret:
        raise HTTPException(
            status_code=500,
            detail="BACKROOMS_INVITE_SECRET is not set in environment.",
        )

    token = sign_invite_token(
        secret=invite_secret,
        room_id=str(room_data.get("id")),
        version=room_data.get("invite_version"),
    )
    activity_log = (
        f"[INVITE GENERATED]-> user_id: {user_id} generated invite "
        f"for room_id: {room_id} version: {room_data.get('invite_version')}"
    )
    await room_handler.log_room_activity(
        room_id,
        user_id,
        RoomActivityTypes.INVITE_CREATED.value,
        activity_log,
    )

    return {"token": token}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)
