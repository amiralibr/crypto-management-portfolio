"""ApprovalRequest ORM model for Kill Switch Two-Person Approval in MVP-0 (M006)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.exchange_account import Base


class ApprovalRequest(Base):
    """Represents a Two-Person Approval workflow record for Kill Switch Resume."""

    __tablename__ = "approval_requests"
    __table_args__ = (
        CheckConstraint(
            "request_type = 'KILL_SWITCH_RESUME'",
            name="ck_approval_requests_type",
        ),
        CheckConstraint(
            "status IN ("
            "'PENDING_FIRST_APPROVAL', 'PENDING_SECOND_APPROVAL', "
            "'APPROVED', 'REJECTED', 'EXPIRED', 'CANCELLED'"
            ")",
            name="ck_approval_requests_status",
        ),
        CheckConstraint(
            "first_approver_id IS NULL OR first_approver_id != requested_by",
            name="ck_approval_requests_first_distinct_from_requester",
        ),
        CheckConstraint(
            "second_approver_id IS NULL OR ("
            "second_approver_id != requested_by AND second_approver_id != first_approver_id"
            ")",
            name="ck_approval_requests_second_distinct",
        ),
        CheckConstraint(
            "(first_approver_role IS NULL OR second_approver_role IS NULL) OR ("
            "first_approver_role != second_approver_role "
            "AND first_approver_role IN ('ADMIN', 'OPERATOR', 'OPERATIONAL') "
            "AND second_approver_role IN ('ADMIN', 'OPERATOR', 'OPERATIONAL')"
            ")",
            name="ck_approval_requests_complementary_roles",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    requested_by_role: Mapped[str] = mapped_column(String(32), nullable=False)
    first_approver_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    first_approver_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    first_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    second_approver_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    second_approver_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    second_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
