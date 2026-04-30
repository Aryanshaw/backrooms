import uuid
from datetime import datetime

from sqlalchemy import select, func
from config.logger import get_logger
from models.message import RoomSummaries
from models.rooms import RoomActivity, RoomActivityTypes, RoomMember

logger = get_logger(__name__)


class MessageHandler:
    def __init__(self, db):
        self.db = db

    async def submit_summary(
        self,
        room_id: str,
        user_id: str,
        content: str,
    ) -> dict:
        """
        - Validate user is an active member of this room (room_members check)
        - Insert new row into room_summaries with content and server-assigned created_at
        - Log SUMMARY_CREATED to room_activity
        - Commit both writes in single transaction
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

                # insert summary row
                new_summary = RoomSummaries(
                    id=uuid.uuid4(),
                    room_id=room_id,
                    summary=content,
                    created_at=datetime.now(),
                )
                session.add(new_summary)

                # log activity
                session.add(RoomActivity(
                    id=uuid.uuid4(),
                    room_id=room_id,
                    user_id=user_id,
                    activity_type=RoomActivityTypes.SUMMARY_CREATED.value,
                    activity_log=f"[SUMMARY CREATED]-> user_id: {user_id} submitted summary for room_id: {room_id}",
                ))

                await session.commit()
                return {"status": "ok"}

        except Exception as e:
            logger.error(f"Failed to submit summary: {str(e)}")
            raise

    async def pull_summaries(
        self,
        room_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> dict:
        """
        - Get total summary count for this room
        - Select summaries ORDER BY created_at DESC LIMIT limit OFFSET offset
        - Reverse result to return in chronological (ascending) order
        - has_more = total > offset + len(results)
        - Return { summaries: [{ id, summary, created_at }], total, has_more }
        """
        try:
            async with self.db.session() as session:
                total_result = await session.execute(
                    select(func.count()).select_from(RoomSummaries).where(
                        RoomSummaries.room_id == room_id
                    )
                )
                total = total_result.scalar()

                rows_result = await session.execute(
                    select(RoomSummaries)
                    .where(RoomSummaries.room_id == room_id)
                    .order_by(RoomSummaries.created_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
                rows = list(reversed(rows_result.scalars().all()))
                has_more = total > offset + len(rows)

                return {
                    "summaries": [row.to_dict() for row in rows],
                    "total": total,
                    "has_more": has_more,
                }

        except Exception as e:
            logger.error(f"Failed to pull summaries: {str(e)}")
            raise
