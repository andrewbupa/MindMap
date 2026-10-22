"""user theme: each person's choice of dark, light or their device's preference

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-23 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("theme", sa.String(length=10), server_default="system", nullable=False),
    )
    op.create_check_constraint("known_theme", "user", "theme IN ('system', 'dark', 'light')")


def downgrade() -> None:
    op.drop_constraint("known_theme", "user", type_="check")
    op.drop_column("user", "theme")
