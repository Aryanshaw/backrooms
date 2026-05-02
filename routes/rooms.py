from fastapi import APIRouter, Header, HTTPException, Request
from typing import Optional
import os
from pydantic import BaseModel

from handlers.room import RoomHandler

router = APIRouter(prefix="/rooms", tags=["rooms"])


class GenerateInviteRequest(BaseModel):
    user_id: Optional[str] = None


@router.post("/{room_id}/invites")
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
    try:
        token = await room_handler.generate_invite(room_id, user_id)
        if not token:
            raise HTTPException(
                status_code=403,
                detail="Only the room owner can generate invites.",
            )
        return {"token": token}
    except Exception as e:
        if "BACKROOMS_INVITE_SECRET" in str(e):
             raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate invite.")
