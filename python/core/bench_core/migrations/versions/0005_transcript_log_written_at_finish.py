"""transcript log written at finish

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-21 12:18:39.044426
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("transcript", "log_uri", existing_type=sa.VARCHAR(length=1000), nullable=True)


def downgrade() -> None:
    op.alter_column("transcript", "log_uri", existing_type=sa.VARCHAR(length=1000), nullable=False)
