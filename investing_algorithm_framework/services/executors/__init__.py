"""Order-execution strategies for the v9.0 phase pipeline.

An :class:`Executor` knows *how* to turn a sized intent into a
broker order. :class:`EmitOrdersPhase` delegates to a single
executor instance configured on the strategy
(``TradingStrategy.executor``).

Two built-in executors ship with the framework:

* :class:`LimitOrderExecutor` — limit orders at ``intent.price``
  (the legacy default — preserves the historical behaviour of
  ``run_strategy``).
* :class:`MarketOrderExecutor` — market orders, useful for live
  trading on venues where queueing a limit is undesirable or in
  backtests where execution-on-next-open semantics are wanted.

User code can supply its own :class:`Executor` subclass (e.g. an
``OcoOrderExecutor`` that brackets each entry) — the phase
pipeline itself is unchanged.
"""
from .base import Executor
from .limit import LimitOrderExecutor
from .market import MarketOrderExecutor

__all__ = [
    "Executor",
    "LimitOrderExecutor",
    "MarketOrderExecutor",
]
