"""create conversation messages

Revision ID: 1fc7b6205b78
Revises:
Create Date: 2026-09-26 20:20:14.985800

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1fc7b6205b78"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE conversation_messages (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            message JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX ix_conversation_messages_user_session_id
        ON conversation_messages (user_id, session_id, id)
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE conversation_messages")
