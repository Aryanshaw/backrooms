import os
import uuid
from datetime import datetime

from sqlalchemy import select, func
from config.logger import get_logger
from models.message import Messages
from models.rooms import RoomMetadata

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
