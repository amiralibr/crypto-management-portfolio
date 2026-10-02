"""Development database seed script for MVP-0 F1 Foundation (Paper-only)."""

import asyncio

from sqlalchemy import select

from app.db.models import ExchangeAccount, Strategy, SystemState
from app.db.session import dispose_db, get_session_factory, init_db


async def seed_foundation_data() -> None:
    """Insert idempotent default Paper account, strategy, and Kill Switch state."""
    init_db()
    session_factory = get_session_factory()
    async with session_factory() as session:
        existing_account = await session.scalar(
            select(ExchangeAccount).where(ExchangeAccount.name == "paper-default")
        )
        if existing_account is None:
            session.add(
                ExchangeAccount(
                    name="paper-default",
                    exchange_name="paper_simulated",
                    mode="PAPER",
                    is_active=True,
                )
            )

        existing_strategy = await session.scalar(
            select(Strategy).where(Strategy.strategy_code == "MVP0_SPOT_LONG_V1")
        )
        if existing_strategy is None:
            session.add(
                Strategy(
                    strategy_code="MVP0_SPOT_LONG_V1",
                    name="MVP-0 Deterministic Spot Long Strategy",
                    timeframe="1H",
                    is_active=True,
                    config_json={"paper_only": True},
                )
            )

        existing_state = await session.scalar(
            select(SystemState).where(SystemState.state_key == "KILL_SWITCH")
        )
        if existing_state is None:
            session.add(
                SystemState(
                    state_key="KILL_SWITCH",
                    is_active=False,
                )
            )

        await session.commit()
    await dispose_db()


if __name__ == "__main__":
    asyncio.run(seed_foundation_data())
