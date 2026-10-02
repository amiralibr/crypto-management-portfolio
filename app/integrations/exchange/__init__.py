"""Exchange integration package for MVP-0 (PaperTradingAdapter and FakeExchangeAdapter only)."""

from app.integrations.exchange.base import (
    PERMITTED_ADAPTER_CLASSES,
    ExchangeAdapter,
    ExchangeAdapterRegistry,
    ExchangeOrderReceipt,
    ExchangePositionSnapshot,
    OrderBookSnapshot,
    TickerQuote,
)
from app.integrations.exchange.errors import (
    ExchangeConnectionError,
    ExchangeError,
    ExchangeOrderRejectedError,
    ExchangeRateLimitError,
    ExchangeReconciliationError,
    ExchangeStaleDataError,
)
from app.integrations.exchange.fake import FakeExchangeAdapter
from app.integrations.exchange.paper import PaperTradingAdapter

__all__ = [
    "ExchangeAdapter",
    "ExchangeAdapterRegistry",
    "ExchangeConnectionError",
    "ExchangeError",
    "ExchangeOrderReceipt",
    "ExchangeOrderRejectedError",
    "ExchangePositionSnapshot",
    "ExchangeRateLimitError",
    "ExchangeReconciliationError",
    "ExchangeStaleDataError",
    "FakeExchangeAdapter",
    "OrderBookSnapshot",
    "PERMITTED_ADAPTER_CLASSES",
    "PaperTradingAdapter",
    "TickerQuote",
]
