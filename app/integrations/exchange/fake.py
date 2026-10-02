"""Deterministic in-memory FakeExchangeAdapter for MVP-0 unit, integration, and chaos tests."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.core.enums import ALLOWED_SYMBOLS
from app.integrations.exchange.base import (
    ExchangeAdapter,
    ExchangeOrderReceipt,
    ExchangePositionSnapshot,
    OrderBookSnapshot,
    TickerQuote,
)
from app.integrations.exchange.errors import (
    ExchangeConnectionError,
    ExchangeOrderRejectedError,
)


class FakeExchangeAdapter(ExchangeAdapter):
    """Deterministic, in-memory simulated exchange adapter with failure injection hooks."""

    name: str = "fake_exchange"

    def __init__(self) -> None:
        now = datetime.now(UTC)
        self._tickers: dict[str, TickerQuote] = {
            "BTC/USDT": TickerQuote(
                symbol="BTC/USDT",
                price=Decimal("60000.00"),
                bid=Decimal("59995.00"),
                ask=Decimal("60005.00"),
                volume_24h=Decimal("500000000.00"),
                timestamp=now,
            ),
            "ETH/USDT": TickerQuote(
                symbol="ETH/USDT",
                price=Decimal("3000.00"),
                bid=Decimal("2999.50"),
                ask=Decimal("3000.50"),
                volume_24h=Decimal("250000000.00"),
                timestamp=now,
            ),
            "BNB/USDT": TickerQuote(
                symbol="BNB/USDT",
                price=Decimal("600.00"),
                bid=Decimal("599.90"),
                ask=Decimal("600.10"),
                volume_24h=Decimal("80000000.00"),
                timestamp=now,
            ),
        }
        self._order_books: dict[str, OrderBookSnapshot] = {
            symbol: OrderBookSnapshot(
                symbol=symbol,
                bid_depth_0_5pct=Decimal("2000000.00"),
                ask_depth_0_5pct=Decimal("2000000.00"),
                spread_pct=Decimal("0.0005"),
                timestamp=now,
            )
            for symbol in ALLOWED_SYMBOLS
        }
        self._step_sizes: dict[str, Decimal] = {
            "BTC/USDT": Decimal("0.00001"),
            "ETH/USDT": Decimal("0.0001"),
            "BNB/USDT": Decimal("0.001"),
        }
        self._orders: dict[str, ExchangeOrderReceipt] = {}
        self._positions: dict[str, ExchangePositionSnapshot] = {}
        self.connection_down: bool = False
        self.fail_next_place_order_count: int = 0
        self.fail_cancel_order: bool = False
        self.partial_fill_ratio: Decimal | None = None
        self.fee_rate: Decimal = Decimal("0.002")
        self.place_order_attempts: list[tuple[str, datetime]] = []

    def set_ticker(
        self,
        symbol: str,
        price: Decimal,
        volume_24h: Decimal = Decimal("500000000.00"),
        timestamp: datetime | None = None,
    ) -> None:
        """Set simulated ticker price and timestamp for testing."""
        ts = timestamp or datetime.now(UTC)
        half_spread = price * Decimal("0.0001")
        self._tickers[symbol] = TickerQuote(
            symbol=symbol,
            price=price,
            bid=price - half_spread,
            ask=price + half_spread,
            volume_24h=volume_24h,
            timestamp=ts,
        )

    def set_order_book(
        self,
        symbol: str,
        bid_depth_0_5pct: Decimal,
        ask_depth_0_5pct: Decimal,
        spread_pct: Decimal,
        timestamp: datetime | None = None,
    ) -> None:
        """Set simulated order book depth and spread for testing."""
        ts = timestamp or datetime.now(UTC)
        self._order_books[symbol] = OrderBookSnapshot(
            symbol=symbol,
            bid_depth_0_5pct=bid_depth_0_5pct,
            ask_depth_0_5pct=ask_depth_0_5pct,
            spread_pct=spread_pct,
            timestamp=ts,
        )

    def set_position(
        self,
        symbol: str,
        quantity: Decimal,
        entry_price: Decimal,
    ) -> None:
        """Set simulated exchange position snapshot for reconciliation tests."""
        self._positions[symbol] = ExchangePositionSnapshot(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            updated_at=datetime.now(UTC),
        )

    def _check_connection(self) -> None:
        if self.connection_down:
            raise ExchangeConnectionError("Simulated exchange connection is down")

    async def get_ticker(self, symbol: str) -> TickerQuote:
        """Return simulated ticker quote or raise ExchangeConnectionError."""
        self._check_connection()
        if symbol not in self._tickers:
            raise ExchangeOrderRejectedError(f"Unsupported symbol: {symbol}")
        return self._tickers[symbol]

    async def get_order_book(self, symbol: str) -> OrderBookSnapshot:
        """Return simulated order book snapshot or raise ExchangeConnectionError."""
        self._check_connection()
        if symbol not in self._order_books:
            raise ExchangeOrderRejectedError(f"Unsupported symbol: {symbol}")
        return self._order_books[symbol]

    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        client_order_id: str,
        limit_price: Decimal | None = None,
    ) -> ExchangeOrderReceipt:
        """Place an order idempotently by client_order_id."""
        now = datetime.now(UTC)
        self.place_order_attempts.append((client_order_id, now))
        self._check_connection()

        if self.fail_next_place_order_count > 0:
            self.fail_next_place_order_count -= 1
            raise ExchangeConnectionError(
                f"Simulated order submission failure for {client_order_id}"
            )

        if client_order_id in self._orders:
            return self._orders[client_order_id]

        if symbol not in ALLOWED_SYMBOLS:
            raise ExchangeOrderRejectedError(f"Symbol {symbol} is not allowed in MVP-0")
        if side not in ("BUY", "SELL"):
            raise ExchangeOrderRejectedError(f"Invalid order side: {side}")
        if quantity <= Decimal("0"):
            raise ExchangeOrderRejectedError("Order quantity must be positive")

        ticker = self._tickers[symbol]
        exec_price = (
            limit_price if (limit_price is not None and order_type == "LIMIT") else ticker.price
        )

        if self.partial_fill_ratio is not None and Decimal("0") < self.partial_fill_ratio < Decimal(
            "1"
        ):
            filled_qty = (quantity * self.partial_fill_ratio).quantize(Decimal("0.000000000001"))
            status = "PARTIALLY_FILLED"
        else:
            filled_qty = quantity
            status = "FILLED"

        fee = (filled_qty * exec_price * self.fee_rate).quantize(Decimal("0.000000000001"))
        receipt = ExchangeOrderReceipt(
            exchange_order_id=f"sim-{uuid.uuid4()}",
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            status=status,
            quantity=quantity,
            filled_quantity=filled_qty,
            average_fill_price=exec_price,
            fee=fee,
            executed_at=now,
        )
        self._orders[client_order_id] = receipt

        current_pos = self._positions.get(symbol)
        if side == "BUY":
            new_qty = (current_pos.quantity if current_pos else Decimal("0")) + filled_qty
            self._positions[symbol] = ExchangePositionSnapshot(
                symbol=symbol,
                quantity=new_qty,
                entry_price=exec_price,
                updated_at=now,
            )
        else:
            existing_qty = current_pos.quantity if current_pos else Decimal("0")
            remaining_qty = max(Decimal("0"), existing_qty - filled_qty)
            if remaining_qty == Decimal("0"):
                self._positions.pop(symbol, None)
            else:
                self._positions[symbol] = ExchangePositionSnapshot(
                    symbol=symbol,
                    quantity=remaining_qty,
                    entry_price=current_pos.entry_price if current_pos else exec_price,
                    updated_at=now,
                )

        return receipt

    async def cancel_order(self, client_order_id: str) -> bool:
        """Cancel an existing simulated order by client_order_id."""
        self._check_connection()
        if self.fail_cancel_order:
            raise ExchangeConnectionError(f"Simulated cancel failure for {client_order_id}")
        existing = self._orders.get(client_order_id)
        if existing is None:
            return False
        if existing.status in ("CANCELLED", "FILLED"):
            return True
        cancelled = ExchangeOrderReceipt(
            exchange_order_id=existing.exchange_order_id,
            client_order_id=existing.client_order_id,
            symbol=existing.symbol,
            side=existing.side,
            order_type=existing.order_type,
            status="CANCELLED",
            quantity=existing.quantity,
            filled_quantity=existing.filled_quantity,
            average_fill_price=existing.average_fill_price,
            fee=existing.fee,
            executed_at=datetime.now(UTC),
        )
        self._orders[client_order_id] = cancelled
        return True

    async def get_order_status(self, client_order_id: str) -> ExchangeOrderReceipt | None:
        """Return simulated order receipt by client_order_id."""
        self._check_connection()
        return self._orders.get(client_order_id)

    async def get_open_orders(self, symbol: str | None = None) -> list[ExchangeOrderReceipt]:
        """Return simulated orders that are currently open or partially filled."""
        self._check_connection()
        open_statuses = {"SUBMITTED", "OPEN", "PARTIALLY_FILLED"}
        return [
            order
            for order in self._orders.values()
            if order.status in open_statuses and (symbol is None or order.symbol == symbol)
        ]

    async def get_positions(self) -> dict[str, ExchangePositionSnapshot]:
        """Return copy of current simulated positions."""
        self._check_connection()
        return dict(self._positions)

    def get_step_size(self, symbol: str) -> Decimal:
        """Return quantity step size for symbol."""
        return self._step_sizes.get(symbol, Decimal("0.00001"))
