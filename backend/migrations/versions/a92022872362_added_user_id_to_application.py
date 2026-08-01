"""added user id to application

Revision ID: a92022872362
Revises: c54297409029
Create Date: 2026-07-20 01:54:02.545786

"""

from typing import Sequence, Union

import sqlmodel
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a92022872362"
down_revision: Union[str, Sequence[str], None] = "c54297409029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("application", sa.Column("owner_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        "fk_application_owner_id_user",
        "application",
        "user",
        ["owner_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_application_owner_id_user", "application", type_="foreignkey"
    )
    op.drop_column("application", "owner_id")
