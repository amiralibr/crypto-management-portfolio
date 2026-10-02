"""SystemState ORM model for persistent Kill Switch state in MVP-0 (M001)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.exchange_account import Base


class SystemState(Base):
    """Persistent system state record including Kill Switch state."""

    __tablename__ = "system_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state_key: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default="KILL_SWITCH"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    activation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    activation_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resume_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resumed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resume_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    exposure_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(6, 4),
        nullable=False,
        default=Decimal("1.0000"),
        server_default="1.0000",
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
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
