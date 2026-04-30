import os
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from config.logger import get_logger
from models.message import Messages, RoomSummaries
from models.rooms import RoomMetadata, RoomActivity, RoomActivityTypes, RoomMember

logger = get_logger(__name__)

SUMMARY_THRESHOLD = int(os.getenv("BACKROOMS_SUMMARY_THRESHOLD", 8000))


class MessageHandler:
    def __init__(self, db):
        self.db = db

    async def push_message(
        self,
        room_id: str,
        user_id: str,
        user_content: str,
        assistant_content: str,
    ) -> dict:
        """
        - Build two Messages rows (message_type: user, message_type: assistant) for this turn
        - Add both to session — they commit together or not at all (single transaction)
        - Query room_metadata for this room — if no row exists yet (first push ever), create one
          with total_tokens seeded to this turn's token count and last_summary_tokens=0
        - Estimate tokens for this turn: (len(user_content) + len(assistant_content)) // 4
        - If metadata already exists, increment total_tokens by estimated tokens
        - Commit everything — messages + metadata update — in one shot
        - Compute tokens_since_summary = total_tokens - last_summary_tokens
        - If tokens_since_summary > SUMMARY_THRESHOLD:
            - If last_summarized_message_id exists: fetch its created_at as an anchor timestamp,
              count all messages in the room created after that timestamp (unsummarized)
            - If last_summarized_message_id is None (no summary ever generated): count all messages in room
            - Return { status: "summary_needed", last_summarized_message_id, unsummarized_message_count }
        - Otherwise return { status: "ok" }
        """
        try:
            async with self.db.session() as session:
                # build user + assistant rows and stage both for insert
                user_msg = Messages(
                    id=uuid.uuid4(),
                    room_id=room_id,
                    user_id=user_id,
                    message_type="user",
                    content=user_content,
                    created_at=datetime.now(),
                )
                assistant_msg = Messages(
                    id=uuid.uuid4(),
                    room_id=room_id,
                    user_id=user_id,
                    message_type="assistant",
                    content=assistant_content,
                    created_at=datetime.now(),
                )
                session.add(user_msg)
                session.add(assistant_msg)

                # fetch existing metadata row; create if this is the first push for this room
                result = await session.execute(
                    select(RoomMetadata).where(RoomMetadata.room_id == room_id)
                )
                metadata = result.scalar_one_or_none()

                new_tokens = (len(user_content) + len(assistant_content)) // 4

                if not metadata:
                    metadata = RoomMetadata(
                        id=uuid.uuid4(),
                        room_id=room_id,
                        total_tokens=new_tokens,
                        last_summary_tokens=0,
                        last_summarized_message_id=None,
                    )
                    session.add(metadata)
                else:
                    metadata.total_tokens = metadata.total_tokens + new_tokens

                # single commit — messages + metadata land together
                await session.commit()

                # check if accumulated tokens since last summary crossed the threshold
                tokens_since_summary = metadata.total_tokens - metadata.last_summary_tokens
                if tokens_since_summary > SUMMARY_THRESHOLD:
                    last_id = metadata.last_summarized_message_id

                    if last_id:
                        # use the last summarized message's timestamp as anchor —
                        # count only messages created after it (not yet summarized)
                        anchor_result = await session.execute(
                            select(Messages.created_at).where(Messages.id == last_id)
                        )
                        anchor_ts = anchor_result.scalar_one_or_none()
                        count_result = await session.execute(
                            select(func.count()).select_from(Messages).where(
                                Messages.room_id == room_id,
                                Messages.created_at > anchor_ts,
                            )
                        )
                    else:
                        # no summary has ever been generated — every message in room is unsummarized
                        count_result = await session.execute(
                            select(func.count()).select_from(Messages).where(
                                Messages.room_id == room_id
                            )
                        )

                    unsummarized_count = count_result.scalar()

                    return {
                        "status": "summary_needed",
                        "last_summarized_message_id": str(last_id) if last_id else None,
                        "unsummarized_message_count": unsummarized_count,
                    }

                return {"status": "ok"}

        except Exception as e:
            logger.error(f"Failed to push message: {str(e)}")
            raise

    async def pull_messages(
        self,
        room_id: str,
        limit: int = 20,
        offset: int = 0,
        after_id: Optional[str] = None,
    ) -> dict:
        """
        - Get total message count for the room (used for has_more calculation)
        - If after_id is provided:
            - Fetch the created_at of the anchor message (the message with that id)
            - Select all messages in the room created after that timestamp, ORDER BY created_at ASC, LIMIT limit
            - has_more = True if there are more messages beyond this page (count after anchor > limit)
        - If no after_id:
            - Select last N messages ORDER BY created_at DESC LIMIT limit OFFSET offset
            - Reverse the result list to return in chronological (ascending) order
            - has_more = True if total_messages > offset + count of returned messages
        - Return { messages: [{ id, message_type, content, created_at }], total_messages, has_more }
        """
        try:
            async with self.db.session() as session:
                # get total count for this room
                total_result = await session.execute(
                    select(func.count()).select_from(Messages).where(
                        Messages.room_id == room_id
                    )
                )
                total_messages = total_result.scalar()

                if after_id:
                    # find anchor message's timestamp
                    anchor_result = await session.execute(
                        select(Messages.created_at).where(Messages.id == after_id)
                    )
                    anchor_ts = anchor_result.scalar_one_or_none()
                    if not anchor_ts:
                        return {
                            "messages": [],
                            "total_messages": total_messages,
                            "has_more": False,
                        }

                    # fetch all messages after the anchor timestamp
                    rows_result = await session.execute(
                        select(Messages)
                        .where(
                            Messages.room_id == room_id,
                            Messages.created_at > anchor_ts,
                        )
                        .order_by(Messages.created_at.asc())
                        .limit(limit)
                    )
                    rows = rows_result.scalars().all()

                    # has_more = more messages exist after the last one in this page
                    has_more = len(rows) == limit and (
                        total_messages - (total_messages - len(rows))
                    ) > 0

                    # simpler: check if there are rows beyond this page
                    if rows:
                        last_ts = rows[-1].created_at
                        beyond_result = await session.execute(
                            select(func.count()).select_from(Messages).where(
                                Messages.room_id == room_id,
                                Messages.created_at > last_ts,
                            )
                        )
                        has_more = beyond_result.scalar() > 0
                    else:
                        has_more = False

                else:
                    # fetch last N messages descending, then reverse for chronological output
                    rows_result = await session.execute(
                        select(Messages)
                        .where(Messages.room_id == room_id)
                        .order_by(Messages.created_at.desc())
                        .limit(limit)
                        .offset(offset)
                    )
                    rows = rows_result.scalars().all()
                    rows = list(reversed(rows))
                    has_more = total_messages > offset + len(rows)

                messages = [
                    {
                        "id": str(row.id),
                        "message_type": row.message_type,
                        "content": row.content,
                        "created_at": str(row.created_at),
                    }
                    for row in rows
                ]

                return {
                    "messages": messages,
                    "total_messages": total_messages,
                    "has_more": has_more,
                }

        except Exception as e:
            logger.error(f"Failed to pull messages: {str(e)}")
            raise

    async def submit_summary(
        self,
        room_id: str,
        user_id: str,
        content: str,
        from_message_id: str,
        to_message_id: str,
    ) -> dict:
        """
        - Validate that the user is an active member of this room (room_members check)
        - Validate that from_message_id exists and belongs to this room
        - Validate that to_message_id exists and belongs to this room
        - Insert new row into room_summaries with content, from_message_id, to_message_id, room_id
        - Fetch room_metadata for this room — if missing, create with defaults
        - Snapshot total_tokens into last_summary_tokens (resets the accumulation counter
          so push_message stops returning summary_needed after this point)
        - Set last_summarized_message_id = to_message_id
        - Log SUMMARY_CREATED to room_activity
        - Commit all three writes (summary insert + metadata update + activity log) in single transaction
        - Return { status: "ok" }
        """
        try:
            async with self.db.session() as session:
                # validate user is active member of this room
                member_result = await session.execute(
                    select(RoomMember).where(
                        RoomMember.room_id == room_id,
                        RoomMember.user_id == user_id,
                        RoomMember.status == "active",
                    )
                )
                if not member_result.scalar_one_or_none():
                    return {"status": "error", "message": "FAILED: user is not an active member of this room"}

                # validate from_message_id exists in this room
                from_msg_result = await session.execute(
                    select(Messages).where(
                        Messages.id == from_message_id,
                        Messages.room_id == room_id,
                    )
                )
                if not from_msg_result.scalar_one_or_none():
                    return {"status": "error", "message": f"FAILED: from_message_id '{from_message_id}' not found in this room"}

                # validate to_message_id exists in this room
                to_msg_result = await session.execute(
                    select(Messages).where(
                        Messages.id == to_message_id,
                        Messages.room_id == room_id,
                    )
                )
                if not to_msg_result.scalar_one_or_none():
                    return {"status": "error", "message": f"FAILED: to_message_id '{to_message_id}' not found in this room"}

                # insert new summary row
                new_summary = RoomSummaries(
                    id=uuid.uuid4(),
                    room_id=room_id,
                    summary=content,
                    from_message_id=from_message_id,
                    to_message_id=to_message_id,
                )
                session.add(new_summary)

                # fetch or create room_metadata
                metadata_result = await session.execute(
                    select(RoomMetadata).where(RoomMetadata.room_id == room_id)
                )
                metadata = metadata_result.scalar_one_or_none()

                if not metadata:
                    metadata = RoomMetadata(
                        id=uuid.uuid4(),
                        room_id=room_id,
                        total_tokens=0,
                        last_summary_tokens=0,
                        last_summarized_message_id=to_message_id,
                    )
                    session.add(metadata)
                else:
                    # snapshot total_tokens → last_summary_tokens to reset accumulation counter
                    metadata.last_summary_tokens = metadata.total_tokens
                    metadata.last_summarized_message_id = to_message_id

                # log activity
                session.add(RoomActivity(
                    id=uuid.uuid4(),
                    room_id=room_id,
                    user_id=user_id,
                    activity_type=RoomActivityTypes.SUMMARY_CREATED.value,
                    activity_log=f"[SUMMARY CREATED]-> from_message_id: {from_message_id}, to_message_id: {to_message_id}",
                ))

                await session.commit()
                return {"status": "ok"}

        except Exception as e:
            logger.error(f"Failed to submit summary: {str(e)}")
            raise
