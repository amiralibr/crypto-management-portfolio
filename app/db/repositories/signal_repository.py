"""Signal persistence repository for MVP-0 Phase F3 (§2.1 & §5.3)."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import SignalNotFoundError
from app.db.models.signal import Signal


class SignalRepository:
    """Async PostgreSQL repository for Signal entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, signal: Signal) -> Signal:
        """Persist a new Signal in the current session and flush."""
        self._session.add(signal)
        await self._session.flush()
        return signal

    async def get_by_id(
        self,
        signal_id: uuid.UUID | str,
        *,
        for_update: bool = False,
    ) -> Signal | None:
        """Retrieve a Signal by primary UUID or business signal_id string."""
        stmt = select(Signal)
        parsed_uuid: uuid.UUID | None = None
        if isinstance(signal_id, uuid.UUID):
            parsed_uuid = signal_id
        else:
            try:
                parsed_uuid = uuid.UUID(str(signal_id))
            except ValueError:
                parsed_uuid = None

        if parsed_uuid is not None:
            stmt = stmt.where(Signal.id == parsed_uuid)
        else:
            stmt = stmt.where(Signal.signal_id == str(signal_id))

        if for_update:
            stmt = stmt.with_for_update()
        return await self._session.scalar(stmt)

    async def get_by_id_or_raise(
        self,
        signal_id: uuid.UUID | str,
        *,
        for_update: bool = False,
    ) -> Signal:
        """Retrieve a Signal by UUID or signal_id string, or raise SignalNotFoundError (404)."""
        signal = await self.get_by_id(signal_id, for_update=for_update)
        if signal is None:
            raise SignalNotFoundError(
                f"Signal '{signal_id}' not found",
                details={"signal_id": str(signal_id)},
            )
        return signal

    async def list_signals(
        self,
        *,
        approval_status: str | None = None,
        symbol: str | None = None,
        limit: int = 100,
    ) -> Sequence[Signal]:
        """List persisted signals ordered by created_at descending."""
        stmt = select(Signal).order_by(Signal.created_at.desc(), Signal.id.desc())
        if approval_status is not None:
            stmt = stmt.where(Signal.approval_status == approval_status)
        if symbol is not None:
            stmt = stmt.where(Signal.symbol == symbol)
        stmt = stmt.limit(limit)
        return list((await self._session.scalars(stmt)).all())
