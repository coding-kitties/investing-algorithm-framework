from unittest import TestCase
from datetime import datetime, timezone
from unittest.mock import MagicMock
import tempfile
import json
from pathlib import Path

from investing_algorithm_framework.app.context import Context
from investing_algorithm_framework.domain import (
    BacktestRun, BACKTESTING_FLAG, INDEX_DATETIME,
)


class TestContextRecord(TestCase):
    """Test the Context.record() method."""

    def _make_context(self, is_backtest=True, index_datetime=None):
        """Create a Context with mocked services."""
        config = {}
        if is_backtest:
            config[BACKTESTING_FLAG] = True
        if index_datetime is not None:
            config[INDEX_DATETIME] = index_datetime

        configuration_service = MagicMock()
        configuration_service.config = config

        context = Context(
            configuration_service=configuration_service,
            portfolio_configuration_service=MagicMock(),
            portfolio_service=MagicMock(),
            position_service=MagicMock(),
            order_service=MagicMock(),
            market_credential_service=MagicMock(),
            trade_service=MagicMock(),
            trade_stop_loss_service=MagicMock(),
            trade_take_profit_service=MagicMock(),
            data_provider_service=MagicMock(),
        )
        return context

    def test_record_stores_values(self):
        dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
        context = self._make_context(is_backtest=True, index_datetime=dt)
        context.record(rsi=70.5, sma=100.0)

        recorded = context.get_recorded_values()
        self.assertIn("rsi", recorded)
        self.assertIn("sma", recorded)
        self.assertEqual(len(recorded["rsi"]), 1)
        self.assertEqual(recorded["rsi"][0], (dt, 70.5))
        self.assertEqual(recorded["sma"][0], (dt, 100.0))

    def test_record_multiple_timestamps(self):
        dt1 = datetime(2023, 1, 1, tzinfo=timezone.utc)
        dt2 = datetime(2023, 1, 2, tzinfo=timezone.utc)
        context = self._make_context(is_backtest=True, index_datetime=dt1)

        context.record(rsi=70.5)

        # Simulate advancing time
        context.configuration_service.config[INDEX_DATETIME] = dt2
        context.record(rsi=65.0)

        recorded = context.get_recorded_values()
        self.assertEqual(len(recorded["rsi"]), 2)
        self.assertEqual(recorded["rsi"][0], (dt1, 70.5))
        self.assertEqual(recorded["rsi"][1], (dt2, 65.0))

    def test_record_noop_in_live_mode(self):
        context = self._make_context(is_backtest=False)
        context.record(rsi=70.5)

        recorded = context.get_recorded_values()
        self.assertEqual(len(recorded), 0)

    def test_record_arbitrary_keys(self):
        dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
        context = self._make_context(is_backtest=True, index_datetime=dt)
        context.record(
            my_custom_indicator=42,
            signal_strength=0.85,
            some_dict={"a": 1},
        )

        recorded = context.get_recorded_values()
        self.assertEqual(len(recorded), 3)
        self.assertEqual(recorded["my_custom_indicator"][0][1], 42)
        self.assertEqual(recorded["signal_strength"][0][1], 0.85)
        self.assertEqual(recorded["some_dict"][0][1], {"a": 1})

    def test_clear_recorded_values(self):
        dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
        context = self._make_context(is_backtest=True, index_datetime=dt)
        context.record(rsi=70.5)
        context.clear_recorded_values()

        recorded = context.get_recorded_values()
        self.assertEqual(len(recorded), 0)


class TestBacktestRunRecordedValues(TestCase):
    """Test recorded_values on BacktestRun serialization."""

    def test_to_dict_includes_recorded_values(self):
        dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
        run = BacktestRun(
            backtest_start_date=dt,
            backtest_end_date=datetime(2023, 12, 31, tzinfo=timezone.utc),
            trading_symbol="USD",
            recorded_values={
                "rsi": [(dt, 70.5)],
                "sma": [(dt, 100.0)],
            },
        )

        d = run.to_dict()
        self.assertIn("recorded_values", d)
        self.assertIn("rsi", d["recorded_values"])
        self.assertEqual(len(d["recorded_values"]["rsi"]), 1)
        self.assertEqual(d["recorded_values"]["rsi"][0]["value"], 70.5)

    def test_save_and_load_recorded_values(self):
        dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
        run = BacktestRun(
            backtest_start_date=dt,
            backtest_end_date=datetime(2023, 12, 31, tzinfo=timezone.utc),
            trading_symbol="USD",
            initial_unallocated=1000.0,
            created_at=dt,
            recorded_values={
                "rsi": [(dt, 70.5), (datetime(2023, 6, 1, tzinfo=timezone.utc), 45.0)],
                "custom_metric": [(dt, {"nested": True})],
            },
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            run.save(tmpdir)
            loaded = BacktestRun.open(tmpdir)

        self.assertIn("rsi", loaded.recorded_values)
        self.assertEqual(len(loaded.recorded_values["rsi"]), 2)
        self.assertEqual(loaded.recorded_values["rsi"][0][1], 70.5)
        self.assertEqual(loaded.recorded_values["rsi"][1][1], 45.0)
        self.assertIn("custom_metric", loaded.recorded_values)
        self.assertEqual(
            loaded.recorded_values["custom_metric"][0][1],
            {"nested": True}
        )

    def test_empty_recorded_values_by_default(self):
        dt = datetime(2023, 1, 1, tzinfo=timezone.utc)
        run = BacktestRun(
            backtest_start_date=dt,
            backtest_end_date=datetime(2023, 12, 31, tzinfo=timezone.utc),
            trading_symbol="USD",
        )
        self.assertEqual(run.recorded_values, {})
        d = run.to_dict()
        self.assertEqual(d["recorded_values"], {})
