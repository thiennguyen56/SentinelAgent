"""create handoff requests

Revision ID: 1326dbb57857
Revises: 1fc7b6205b78
Create Date: 2026-09-28 15:33:33.611803

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1326dbb57857"
down_revision: Union[str, Sequence[str], None] = "1fc7b6205b78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE handoff_requests (
            id UUID PRIMARY KEY,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            summary TEXT NOT NULL,
            entity_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            priority TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CHECK (jsonb_typeof(entity_ids) = 'array'),
            CHECK (priority IN ('normal', 'high')),
            CHECK (status IN (
                'pending', 'approved', 'rejected', 'expired', 'executed', 'failed'
            ))
        )
    """)

    op.execute("""
        CREATE INDEX ix_handoff_requests_user_session
        ON handoff_requests (user_id, session_id, created_at DESC)
    """)


def downgrade() -> None:
    """Downgrade schema."""

    op.execute("""
        DROP INDEX ix_handoff_requests_user_session
    """)

    op.execute("""
        DROP TABLE handoff_requests
    """)
