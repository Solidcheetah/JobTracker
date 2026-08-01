"""added notes to application

Revision ID: 3f25930cc588
Revises: 8cc95fdc7d24
Create Date: 2026-07-24 00:11:40.723602

"""

from typing import Sequence, Union

import sqlmodel
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3f25930cc588"
down_revision: Union[str, Sequence[str], None] = "8cc95fdc7d24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "application",
        sa.Column("note", sa.String(length=2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("application", "note")
