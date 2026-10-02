"""Abstract base exchange adapter and value objects for MVP-0 (Paper-only)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.integrations.exchange.errors import ExchangeError

PERMITTED_ADAPTER_CLASSES: frozenset[str] = frozenset(
    {"PaperTradingAdapter", "FakeExchangeAdapter"}
)
PERMITTED_ADAPTERS: frozenset[str] = PERMITTED_ADAPTER_CLASSES


@dataclass(frozen=True)
class TickerQuote:
    """Immutable market ticker quote with Decimal prices and UTC timestamp."""

    symbol: str
    price: Decimal
    bid: Decimal
    ask: Decimal
    volume_24h: Decimal
    timestamp: datetime


@dataclass(frozen=True)
class OrderBookSnapshot:
    """Immutable order book depth and spread snapshot."""

    symbol: str
    bid_depth_0_5pct: Decimal
    ask_depth_0_5pct: Decimal
    spread_pct: Decimal
    timestamp: datetime


@dataclass(frozen=True)
class ExchangeOrderReceipt:
    """Immutable receipt returned by an exchange adapter for an order."""

    exchange_order_id: str
    client_order_id: str
    symbol: str
    side: str
    order_type: str
    status: str
    quantity: Decimal
    filled_quantity: Decimal
    average_fill_price: Decimal | None
    fee: Decimal
    executed_at: datetime


@dataclass(frozen=True)
class ExchangePositionSnapshot:
    """Immutable exchange-side position snapshot used for reconciliation."""

    symbol: str
    quantity: Decimal
    entry_price: Decimal
    updated_at: datetime


class ExchangeAdapter(ABC):
    """Abstract base interface for MVP-0 Paper/Fake exchange adapters."""

    name: str = "abstract_exchange"

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if cls.__name__ not in PERMITTED_ADAPTER_CLASSES:
            raise ExchangeError(
                f"Adapter '{cls.__name__}' is forbidden in MVP-0; "
                f"only {sorted(PERMITTED_ADAPTER_CLASSES)} are allowed."
            )

    @abstractmethod
    async def get_ticker(self, symbol: str) -> TickerQuote:
        """Fetch latest ticker quote for symbol."""

    @abstractmethod
    async def get_order_book(self, symbol: str) -> OrderBookSnapshot:
        """Fetch latest order book depth and spread for symbol."""

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        client_order_id: str,
        limit_price: Decimal | None = None,
    ) -> ExchangeOrderReceipt:
        """Place a simulated Spot order idempotently by client_order_id."""

    @abstractmethod
    async def cancel_order(self, client_order_id: str) -> bool:
        """Cancel an open simulated order by client_order_id."""

    @abstractmethod
    async def get_order_status(self, client_order_id: str) -> ExchangeOrderReceipt | None:
        """Get current status of an order by client_order_id."""

    @abstractmethod
    async def get_open_orders(self, symbol: str | None = None) -> list[ExchangeOrderReceipt]:
        """List all currently open orders on the simulated exchange."""

    @abstractmethod
    async def get_positions(self) -> dict[str, ExchangePositionSnapshot]:
        """Return simulated exchange positions keyed by symbol."""

    @abstractmethod
    def get_step_size(self, symbol: str) -> Decimal:
        """Return minimum quantity step size for symbol."""


class ExchangeAdapterRegistry:
    """Registry of permitted MVP-0 exchange adapters with provider health scoring."""

    def __init__(self) -> None:
        self._adapters: dict[str, ExchangeAdapter] = {}
        self._scores: dict[str, Decimal] = {}

    def register(self, name: str, adapter: ExchangeAdapter) -> None:
        """Register a permitted Paper or Fake exchange adapter."""
        if type(adapter).__name__ not in PERMITTED_ADAPTER_CLASSES:
            raise ExchangeError(
                f"Cannot register forbidden adapter class '{type(adapter).__name__}'"
            )
        self._adapters[name] = adapter
        self._scores[name] = Decimal("1.0")

    def get(self, name: str) -> ExchangeAdapter:
        """Retrieve adapter by registered name."""
        if name not in self._adapters:
            raise ExchangeError(f"Exchange adapter '{name}' is not registered")
        return self._adapters[name]

    def get_best(self) -> ExchangeAdapter:
        """Retrieve the highest-scoring registered adapter."""
        if not self._adapters:
            raise ExchangeError("No exchange adapters registered")
        best_name = max(self._scores, key=lambda k: self._scores[k])
        return self._adapters[best_name]

    def update_score(self, name: str, score: Decimal) -> None:
        """Update provider health score in [0, 1]."""
        if name not in self._adapters:
            raise ExchangeError(f"Exchange adapter '{name}' is not registered")
        self._scores[name] = score
