"""ExchangeAccount ORM model for MVP-0 (M001)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarative class for all MVP-0 SQLAlchemy models."""


class ExchangeAccount(Base):
    """Represents a Paper-only exchange account abstraction."""

    __tablename__ = "exchange_accounts"
    __table_args__ = (CheckConstraint("mode = 'PAPER'", name="ck_exchange_accounts_paper_only"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    exchange_name: Mapped[str] = mapped_column(String(32), nullable=False)
    mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="PAPER", server_default="PAPER"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
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
