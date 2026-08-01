"""enable rls

Revision ID: 5a63a33e7313
Revises: a92022872362
Create Date: 2026-07-20 15:53:58.939558

"""

from typing import Sequence, Union

import sqlmodel
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5a63a33e7313"
down_revision: Union[str, Sequence[str], None] = "a92022872362"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE application ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE application FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY application_owner_isolation ON application
        USING (owner_id = current_setting('app.current_user_id', true)::uuid)
        WITH CHECK (owner_id = current_setting('app.current_user_id', true)::uuid)
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP POLICY IF EXISTS application_owner_isolation ON application")
    op.execute("ALTER TABLE application DISABLE ROW LEVEL SECURITY")
