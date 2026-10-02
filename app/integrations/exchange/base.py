"""Reserved exchange adapter base definition (Paper-only; no live adapter allowed)."""

PERMITTED_ADAPTERS: frozenset[str] = frozenset({"PaperTradingAdapter", "FakeExchangeAdapter"})
