"""M006 — kill_switch_dual_approval: approval_requests."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_kill_switch_dual_approval"
down_revision: str | None = "0005_outbox_and_audit"
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None


def upgrade() -> None:
    """Create approval_requests table."""
    op.create_table(
        "approval_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_type", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requested_by_role", sa.String(length=32), nullable=False),
        sa.Column("first_approver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("first_approver_role", sa.String(length=32), nullable=True),
        sa.Column("first_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("second_approver_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("second_approver_role", sa.String(length=32), nullable=True),
        sa.Column("second_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "request_type = 'KILL_SWITCH_RESUME'",
            name="ck_approval_requests_type",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'PENDING_FIRST_APPROVAL', 'PENDING_SECOND_APPROVAL', "
            "'APPROVED', 'REJECTED', 'EXPIRED', 'CANCELLED'"
            ")",
            name="ck_approval_requests_status",
        ),
        sa.CheckConstraint(
            "first_approver_id IS NULL OR first_approver_id != requested_by",
            name="ck_approval_requests_first_distinct_from_requester",
        ),
        sa.CheckConstraint(
            "second_approver_id IS NULL OR ("
            "second_approver_id != requested_by AND second_approver_id != first_approver_id"
            ")",
            name="ck_approval_requests_second_distinct",
        ),
        sa.CheckConstraint(
            "(first_approver_role IS NULL OR second_approver_role IS NULL) OR ("
            "first_approver_role != second_approver_role "
            "AND first_approver_role IN ('ADMIN', 'OPERATOR', 'OPERATIONAL') "
            "AND second_approver_role IN ('ADMIN', 'OPERATOR', 'OPERATIONAL')"
            ")",
            name="ck_approval_requests_complementary_roles",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop approval_requests table."""
    op.drop_table("approval_requests")
