"""add status and role to room members

Revision ID: a9d7f4c1b2e3
Revises: 8d311336cf54
Create Date: 2026-04-29 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9d7f4c1b2e3'
down_revision: Union[str, None] = '8d311336cf54'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "room_members",
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
    )
    op.add_column(
        "room_members",
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
    )

    op.execute(
        """
        UPDATE room_members
        SET role = CASE
            WHEN room_members.user_id = rooms.owner_id THEN 'owner'
            ELSE 'member'
        END
        FROM rooms
        WHERE room_members.room_id = rooms.id
        """
    )

    op.alter_column("room_members", "status", server_default=None)
    op.alter_column("room_members", "role", server_default=None)


def downgrade() -> None:
    op.drop_column("room_members", "role")
    op.drop_column("room_members", "status")
