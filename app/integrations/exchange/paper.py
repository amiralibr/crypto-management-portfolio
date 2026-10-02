"""PaperTradingAdapter for isolated Paper Trading execution in MVP-0."""

from decimal import Decimal

from app.core.config import Settings, get_settings
from app.integrations.exchange.base import ExchangeOrderReceipt
from app.integrations.exchange.errors import ExchangeError
from app.integrations.exchange.fake import FakeExchangeAdapter


class PaperTradingAdapter(FakeExchangeAdapter):
    """Paper-only execution adapter enforcing LIVE_TRADING=false and PAPER_TRADING=true."""

    name: str = "paper_trading"

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        active_settings = settings or get_settings()
        self._enforce_paper_mode(active_settings)
        self._settings = active_settings

    @staticmethod
    def _enforce_paper_mode(settings: Settings) -> None:
        if settings.LIVE_TRADING is not False or settings.PAPER_TRADING is not True:
            raise ExchangeError(
                "PaperTradingAdapter requires LIVE_TRADING=false and PAPER_TRADING=true"
            )

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        client_order_id: str,
        limit_price: Decimal | None = None,
    ) -> ExchangeOrderReceipt:
        """Verify Paper-only mode before placing a simulated Paper order."""
        self._enforce_paper_mode(self._settings)
        return await super().place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            client_order_id=client_order_id,
            limit_price=limit_price,
        )
