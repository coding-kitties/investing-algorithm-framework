"""Universe descriptor for multi-universe backtest studies.

A :class:`Universe` represents a tradable asset set evaluated under a
single strategy configuration. Multiple universes can be attached to one
:class:`Backtest` envelope so a single params hypothesis can be measured
across several baskets in one bundle (design: tiered-backtest-storage v4
multi-universe envelope).

The corresponding per-run linkage is the free-form
``BacktestRun.metadata["universe_key"]`` tag — a run belongs to the
:class:`Universe` whose ``key`` matches that tag. Runs without a
``universe_key`` are treated as the default (single-universe) bundle
mode.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Universe:
    """
    A named tradable asset set. A universe represents a single "basket" of assets that a strategy is evaluated on. A study can contain multiple universes, each with its own set of assets and metadata, but all sharing the same strategy configuration. This allows for easy comparison of strategy performance across different asset sets while keeping the strategy parameters constant.

    Attributes:
        key: Stable identifier used to tag runs and as the dict key in
            ``Backtest.vector_summaries_by_universe`` /
            ``Backtest.event_summaries_by_universe``. Should be unique
            within one :class:`Backtest`.
        symbols: Tradable symbols (e.g. ``["BTC", "ETH"]``).
        trading_symbol: Quote / accounting currency (e.g. ``"EUR"``).
        market: Exchange identifier (e.g. ``"BITVAVO"``).
        metadata: Optional free-form notes (data source tags, basket
            provenance, etc.).
        initial_capital: Optional initial capital for the universe.
    """
    key: Optional[str] = None
    symbols: List[str] = field(default_factory=list)
    trading_symbol: Optional[str] = None
    market: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    initial_capital: Optional[float] = None
    risk_free_rate: Optional[float] = 0.027 # Default risk-free rate

    # Post initialization generate the key if not provided
    def __post_init__(self):
        if self.key is None:
            self.key = self.generate_key()

    def generate_key(self) -> str:
        """
        Generate a stable key based on the symbols, trading symbol,
        market, initial capital, and risk-free rate.
        """
        symbols_str = ",".join(sorted(self.symbols))
        return f"{symbols_str}|{self.trading_symbol}|{self.market}|{self.initial_capital}|{self.risk_free_rate}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "symbols": list(self.symbols),
            "trading_symbol": self.trading_symbol,
            "market": self.market,
            "metadata": dict(self.metadata),
            "initial_capital": self.initial_capital,
            "risk_free_rate": self.risk_free_rate,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Universe":
        if data is None:
            return None
        return cls(
            key=data.get("key"),
            symbols=list(data.get("symbols") or []),
            trading_symbol=data.get("trading_symbol"),
            market=data.get("market"),
            metadata=dict(data.get("metadata") or {}),
            initial_capital=data.get("initial_capital"),
            risk_free_rate=data.get("risk_free_rate"),
        )
