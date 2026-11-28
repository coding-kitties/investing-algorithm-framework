"""Shared setup and real RSI/EMA signals for capability scenarios.

Eligibility-only checks below use production phases without executing
orders or filling pending ones. Scheduled execution/fill tests instead
use the public StrategyScenario.step API.
"""

from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

import pandas as pd

from investing_algorithm_framework import StrategyScenario
from investing_algorithm_framework.services.data_providers \
    .data_provider_service import DataProviderService
from investing_algorithm_framework.services.strategy_phases import (
    CollectSignalsPhase,
    PhaseState,
    ResolveConflictsPhase,
)
from tests.resources.strategies_for_testing.confluence_strategy import (
    ConfluenceScoringStrategy,
)


START = datetime(2025, 1, 15, tzinfo=timezone.utc)
BAR = timedelta(hours=2)


class EvaluationFrameworkTestCase(TestCase):
    def setUp(self):
        super().setUp()
        for target in ("socket.socket.connect", "socket.create_connection"):
            patcher = patch(target, side_effect=self.reject_connection)
            patcher.start()
            self.addCleanup(patcher.stop)

    def reject_connection(self, *args, **kwargs):
        self.fail("Evaluation scenarios must not access the network")


def scenario(strategy: ConfluenceScoringStrategy, **kwargs):
    return StrategyScenario(
        strategy,
        initial_cash=1_000,
        start=START,
        trading_symbol="EUR",
        **kwargs,
    )


def market_data(signal):
    close = [100 + i for i in range(100)]
    if signal == "entry":
        close += [199 - i * 0.5 for i in range(20)]
    index = pd.date_range(
        end=START - BAR, periods=len(close), freq="2h", tz="UTC",
    )
    prices = pd.Series(close, index=index, dtype=float)
    return {"BTC_ohlcv": pd.DataFrame({
        "Open": prices,
        "High": prices + 1,
        "Low": prices - 1,
        "Close": prices,
        "Volume": 1_000.,
    })}


def collect_and_resolve(seeded, signal="entry"):
    strategy = seeded.strategy
    context = seeded.context
    strategy.context = context
    data = market_data(signal)
    state = PhaseState(
        strategy=strategy,
        context=context,
        data=data,
        current_datetime=seeded.now,
    )
    CollectSignalsPhase().run(state)
    # Position-mode lookup values held assets through the ticker service.
    price = float(data["BTC_ohlcv"]["Close"].iloc[-1])
    with patch.object(
        DataProviderService, "get_ticker_data",
        return_value={"bid": price, "ask": price},
    ):
        ResolveConflictsPhase().run(state)
    return state
