"""Exchange adapter error hierarchy for MVP-0 (Paper-only)."""


class ExchangeError(Exception):
    """Base exception for simulated/paper exchange adapter operations."""


class ExchangeConnectionError(ExchangeError):
    """Raised when the exchange adapter is unreachable or connection fails."""


class ExchangeStaleDataError(ExchangeError):
    """Raised when market data is stale beyond the allowed freshness threshold."""


class ExchangeOrderRejectedError(ExchangeError):
    """Raised when the exchange adapter rejects an order."""


class ExchangeRateLimitError(ExchangeError):
    """Raised when exchange adapter rate limits are exceeded."""


class ExchangeReconciliationError(ExchangeError):
    """Raised when local and simulated exchange states diverge."""
