"""Added reminders

Revision ID: fb67c1505d9a
Revises: 3f25930cc588
Create Date: 2026-07-31 15:09:10.049068

"""

from typing import Sequence, Union

import sqlmodel
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fb67c1505d9a"
down_revision: Union[str, Sequence[str], None] = "3f25930cc588"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


reminder_status = sa.Enum(
    "pending",
    "queued",
    "delivered",
    "failed",
    "cancelled",
    name="reminderstatus",
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "reminder",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.String(length=500), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", reminder_status, nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reminder_owner_id"), "reminder", ["owner_id"])

    # The scanner's hot query is "pending rows whose time has come". Restricting
    # the index to status = 'pending' keeps it proportional to the backlog rather
    # than to the table, so it does not grow as reminders are delivered.
    op.create_index(
        "ix_reminder_due",
        "reminder",
        ["remind_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    # Same ownership isolation as `application`. Note this applies to the API's
    # unprivileged role only: the scanner reads across all owners and therefore
    # has to connect as a role that bypasses RLS.
    op.execute("ALTER TABLE reminder ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE reminder FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY reminder_owner_isolation ON reminder
        USING (owner_id = current_setting('app.current_user_id', true)::uuid)
        WITH CHECK (owner_id = current_setting('app.current_user_id', true)::uuid)
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP POLICY IF EXISTS reminder_owner_isolation ON reminder")
    op.execute("ALTER TABLE reminder DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_reminder_due", table_name="reminder")
    op.drop_index(op.f("ix_reminder_owner_id"), table_name="reminder")
    op.drop_table("reminder")
    # drop_table leaves the enum type behind, which would make a subsequent
    # upgrade fail with "type reminderstatus already exists".
    reminder_status.drop(op.get_bind(), checkfirst=True)
