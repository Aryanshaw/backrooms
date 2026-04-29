"""add status, role, and invite version support

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
    op.execute(
        """
        ALTER TABLE rooms
        ADD COLUMN IF NOT EXISTS invite_version INTEGER NOT NULL DEFAULT 1
        """
    )
    op.execute(
        """
        ALTER TABLE room_members
        ADD COLUMN IF NOT EXISTS status VARCHAR NOT NULL DEFAULT 'active'
        """
    )
    op.execute(
        """
        ALTER TABLE room_members
        ADD COLUMN IF NOT EXISTS role VARCHAR NOT NULL DEFAULT 'member'
        """
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

    op.execute(
        """
        ALTER TABLE rooms
        ALTER COLUMN invite_version DROP DEFAULT
        """
    )
    op.execute(
        """
        ALTER TABLE room_members
        ALTER COLUMN status DROP DEFAULT
        """
    )
    op.execute(
        """
        ALTER TABLE room_members
        ALTER COLUMN role DROP DEFAULT
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE rooms
        DROP COLUMN IF EXISTS invite_version
        """
    )
    op.execute(
        """
        ALTER TABLE room_members
        DROP COLUMN IF EXISTS role
        """
    )
    op.execute(
        """
        ALTER TABLE room_members
        DROP COLUMN IF EXISTS status
        """
    )
