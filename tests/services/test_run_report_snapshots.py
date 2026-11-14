from unittest import TestCase
from copy import deepcopy

import pandas as pd
import polars as pl

from investing_algorithm_framework import DataSource
from investing_algorithm_framework.services.run_reports.snapshot import (
    data_source_snapshots,
    confluence_score_snapshots,
    protective_exit_snapshots,
)
from investing_algorithm_framework.services.order_service.order_service import \
    OrderService


class TestProtectiveExitSnapshots(TestCase):
    def order(self, **changes):
        return {
            "id": "risk-1", "strategy_id": "alpha", "target_symbol": "BTC",
            "order_side": "SELL", "amount": 2, "filled": 0,
            "price": 89, "status": "OPEN",
            "created_at": "2025-01-01T00:00:00+00:00",
            "updated_at": "2025-01-01T00:00:00+00:00",
            "metadata": {
                "order_reason": "stop_loss",
                "protective_trigger": {
                    "timestamp": "2025-01-01T00:00:00+00:00",
                    "price": 90,
                    "rules": [{"rule_id": 3, "threshold_price": 95, "trailing": True}],
                    "trades": [{"trade_id": 4, "amount": 2}],
                },
            }, **changes,
        }

    def test_trigger_retains_observation_and_rule_details(self):
        order = self.order()
        records = protective_exit_snapshots([order])
        event, = records["stop_losses"]
        self.assertEqual([], records["take_profits"])
        self.assertEqual("trigger", event["event_type"])
        self.assertEqual(90, event["price"])
        self.assertTrue(event["rules"][0]["trailing"])
        order["metadata"]["protective_trigger"]["rules"].clear()
        self.assertEqual(3, event["rules"][0]["rule_id"])

    def test_partial_fills_are_retained_and_cancel_does_not_invent_a_fill(self):
        order = self.order()
        metadata = order["metadata"]
        for previous, filled, price, timestamp in (
            (0, .5, 91, "2025-01-01T01:00:00+00:00"),
            (.5, 1, 92, "2025-01-01T02:00:00+00:00"),
        ):
            OrderService._append_protective_fill(
                metadata, previous, filled, price, timestamp, "OPEN",
            )
        OrderService._append_protective_fill(
            metadata, 1, 1, 99, "2025-01-01T03:00:00+00:00", "CANCELED",
        )
        order.update(
            filled=1, status="CANCELED",
            updated_at="2025-01-01T03:00:00+00:00",
        )
        events = protective_exit_snapshots([order])["stop_losses"]
        self.assertEqual(["trigger", "fill", "fill"], [e["event_type"] for e in events])
        self.assertEqual([90, 91, 92], [e["price"] for e in events])
        self.assertEqual([.5, .5], [e["amount"] for e in events[1:]])
        self.assertEqual([.5, 1], [e["filled_amount"] for e in events[1:]])
        self.assertEqual("2025-01-01T02:00:00+00:00", events[-1]["timestamp"])
        self.assertEqual([0, 1], [e["sequence"] for e in events[1:]])

    def test_resting_mirror_is_not_a_trigger_and_cover_is_a_short_exit(self):
        order = self.order(
            order_side="COVER", stop_price=95,
            metadata={
                "order_reason": "take_profit_mirror",
                "_mirror_trade_id": 4,
                "protective_rules": [{"rule_id": 3, "threshold_price": 95}],
            },
        )
        self.assertEqual([], protective_exit_snapshots([order])["take_profits"])
        order["triggered_at"] = "2025-01-01T01:00:00+00:00"
        event, = protective_exit_snapshots([order])["take_profits"]
        self.assertEqual("short", event["direction"])
        self.assertEqual(95, event["price"])
        self.assertEqual("threshold", event["price_source"])
        order["filled"] = 2
        OrderService._append_protective_fill(
            order["metadata"], 0, 2, 94, "2025-01-01T02:00:00+00:00", "CLOSED",
        )
        events = protective_exit_snapshots([order])["take_profits"]
        self.assertEqual(["trigger", "fill"], [e["event_type"] for e in events])
        self.assertEqual(94, events[-1]["price"])

    def test_legacy_explicit_reasons_are_supported_but_ordinary_orders_are_not_guessed(self):
        order = self.order(metadata={"order_reason": "stop_loss"}, filled=2)
        events = protective_exit_snapshots([order])["stop_losses"]
        self.assertEqual(["trigger", "fill"], [e["event_type"] for e in events])
        self.assertEqual([], events[0]["rules"])
        self.assertEqual("legacy_order_price", events[1]["price_source"])
        self.assertEqual(
            {"stop_losses": [], "take_profits": []},
            protective_exit_snapshots([self.order(metadata={})]),
        )

    def test_missing_or_invalid_fill_time_is_an_error(self):
        for timestamp in (None, "not-a-date"):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                protective_exit_snapshots([
                    self.order(filled=2, updated_at=timestamp),
                ])


class TestConfluenceScoreSnapshots(TestCase):
    def test_blocking_details_are_detached_and_do_not_leak_into_later_outcomes(self):
        details = {"cooldown_bars": 12, "remaining_bars": 5}
        signal = {
            "symbol": "BTC", "side": "open_long", "source": "entry",
            "status": "rejected", "reason": "resolve_conflicts.cooldown_rule",
            "reason_details": details,
        }
        record, = confluence_score_snapshots(
            evaluated=[self.card()], signals=[signal],
        )
        self.assertEqual(details, record["signal_reason_details"])
        details["remaining_bars"] = 1
        self.assertEqual(5, record["signal_reason_details"]["remaining_bars"])
        later, = confluence_score_snapshots(evaluated=[record], signals=[])
        self.assertNotIn("signal_reason_details", later)

    def test_skipped_exit_has_no_fabricated_score_or_qualification(self):
        card = {
            "card_id": "exit", "symbol": "BTC", "side": "close_long",
            "evaluation_status": "skipped",
            "signal_reason": "confluence.long_exit_requires_position",
        }
        record, = confluence_score_snapshots(evaluated=[card], signals=[])
        self.assertEqual("not_triggered", record["signal_status"])
        self.assertIsNone(record["signal_strength"])
        self.assertNotIn("score", record)
        self.assertNotIn("qualified", record)
        record, = confluence_score_snapshots(evaluated=[card], signals=None)
        self.assertEqual("unknown", record["signal_status"])

    def card(self, **kwargs):
        return {
            "card_id": "entry", "symbol": "BTC", "side": "open_long",
            "ready": True, "qualified": True, "primary_triggered": True,
            "decision": "QUALIFIED", **kwargs,
        }

    def test_pipeline_outcomes_do_not_overwrite_card_qualification(self):
        for status, reason in (
            ("approved", None),
            ("rejected", "resolve_conflicts.state_block_open"),
            ("rejected", "apply_cooldowns.blocked"),
        ):
            with self.subTest(status=status, reason=reason):
                card = self.card()
                original = deepcopy(card)
                signal = {
                    "symbol": "BTC", "side": "open_long", "source": "entry",
                    "status": status, "reason": reason,
                }
                record, = confluence_score_snapshots(
                    evaluated=[card], signals=[signal],
                )
                self.assertEqual(status, record["signal_status"])
                self.assertEqual(reason, record["signal_reason"])
                self.assertTrue(record["qualified"])
                self.assertEqual("QUALIFIED", record["decision"])
                self.assertEqual(original, card)

    def test_signal_matching_is_specific_to_symbol_side_and_card(self):
        signal = {
            "symbol": "ETH", "side": "open_long", "source": "entry",
            "status": "approved", "reason": None,
        }
        for change in (
            {}, {"symbol": "BTC", "side": "close_long"},
            {"symbol": "BTC", "source": "other"},
        ):
            record, = confluence_score_snapshots(
                evaluated=[self.card()], signals=[{**signal, **change}],
            )
            self.assertEqual("not_emitted", record["signal_status"])
            self.assertEqual(
                "confluence.signal_not_emitted", record["signal_reason"],
            )

    def test_readiness_qualification_and_stage_gates_have_distinct_reasons(self):
        for changes, reason in (
            ({"ready": False}, "confluence.indicators_not_ready"),
            ({"qualified": False}, "confluence.not_qualified"),
            ({"signal_reason": "confluence.scale_in_requires_position"},
             "confluence.scale_in_requires_position"),
            ({"signal_reason": "confluence.scale_in_stage_inactive"},
             "confluence.scale_in_stage_inactive"),
            ({"signal_reason": "confluence.scale_in_stage_completed"},
             "confluence.scale_in_stage_completed"),
        ):
            with self.subTest(reason=reason):
                record, = confluence_score_snapshots(
                    evaluated=[self.card(**changes)], signals=[],
                )
                self.assertEqual("not_emitted", record["signal_status"])
                self.assertEqual(reason, record["signal_reason"])

    def test_failed_execution_never_looks_like_pipeline_approval(self):
        record, = confluence_score_snapshots(
            evaluated=[self.card()], signals=None,
        )
        self.assertEqual("unknown", record["signal_status"])
        self.assertEqual(
            "strategy.execution_incomplete", record["signal_reason"],
        )

    def test_outcomes_are_tick_local(self):
        card = self.card()
        approved = {
            "symbol": "BTC", "side": "open_long", "source": "entry",
            "status": "approved", "reason": None,
        }
        first, = confluence_score_snapshots(evaluated=[card], signals=[approved])
        second, = confluence_score_snapshots(evaluated=[card], signals=[])
        self.assertEqual("approved", first["signal_status"])
        self.assertEqual("not_emitted", second["signal_status"])
        self.assertNotIn("signal_status", card)


class TestDataSourceSnapshots(TestCase):
    def snapshot(self, raw, *, as_of="2020-01-01T04:00:00Z", **kwargs):
        source = DataSource(
            identifier="prices", symbol="BTC/EUR", **kwargs,
        )
        return data_source_snapshots(
            strategy_id="alpha", timestamp=pd.Timestamp(as_of),
            sources=[source], data={"prices": raw},
        )[0]

    def test_only_latest_completed_ohlcv_row_is_captured(self):
        frame = pd.DataFrame({
            "Open": [1., 2., 999.], "High": [3., 4., 999.],
            "Low": [0., 1., 999.], "Close": [2., 3., 999.],
            "Volume": [10., 20., 999.],
        }, index=pd.date_range("2020-01-01", periods=3, freq="2h"))
        original = frame.copy(deep=True)
        record = self.snapshot(frame, data_type="ohlcv", time_frame="2h")
        self.assertEqual(
            "2020-01-01T02:00:00+00:00", record["source_timestamp"],
        )
        self.assertEqual("2020-01-01T04:00:00+00:00", record["timestamp"])
        self.assertEqual({
            "Open": 2., "High": 4., "Low": 1., "Close": 3., "Volume": 20.,
        }, record["values"])
        self.assertEqual("OHLCV", record["data_type"])
        self.assertEqual("2h", record["time_frame"])
        self.assertEqual("BTC/EUR", record["symbol"])
        self.assertEqual("alpha", record["strategy_id"])
        pd.testing.assert_frame_equal(frame, original)
        polars = pl.from_pandas(frame.rename_axis("Datetime").reset_index())
        self.assertEqual(
            record["values"],
            {key: value for key, value in self.snapshot(
                polars, data_type="ohlcv", time_frame="2h",
            )["values"].items() if key != "Datetime"},
        )

    def test_no_completed_bar_and_empty_input_remain_unavailable(self):
        frame = pd.DataFrame(
            {"Close": [999.]},
            index=pd.DatetimeIndex(["2020-01-01T04:00:00Z"]),
        )
        for raw in (frame, frame.iloc[:0]):
            record = self.snapshot(raw, data_type="ohlcv", time_frame="2h")
            self.assertIsNone(record["source_timestamp"])
            self.assertEqual({}, record["values"])

    def test_calendar_month_completion_is_not_a_fixed_duration(self):
        frame = pd.DataFrame(
            {"Close": [1., 2.]},
            index=pd.DatetimeIndex(["2020-01-01", "2020-02-01"]),
        )
        record = self.snapshot(
            frame, as_of="2020-02-29T23:59:00Z",
            data_type="ohlcv", time_frame="1M",
        )
        self.assertEqual(1., record["values"]["Close"])

    def test_ohlcv_requires_timestamped_frames_and_a_timeframe(self):
        with self.assertRaisesRegex(TypeError, "DataFrame"):
            self.snapshot(
                {"Close": 999}, data_type="ohlcv", time_frame="2h",
            )
        with self.assertRaisesRegex(ValueError, "time_frame"):
            self.snapshot(pd.DataFrame(), data_type="ohlcv")

    def test_custom_source_uses_row_timestamp_without_candle_offset(self):
        frame = pd.DataFrame({
            "timestamp": pd.date_range("2020-01-01", periods=3, freq="2h"),
            "sentiment": pd.array([1., pd.NA, 999.], dtype="Float64"),
        })
        record = self.snapshot(
            frame, as_of="2020-01-01T02:00:00Z", data_type="custom",
        )
        self.assertIsNone(record["values"]["sentiment"])
        self.assertEqual(
            "2020-01-01T02:00:00+00:00", record["source_timestamp"],
        )

    def test_ticker_mapping_is_detached_and_excludes_future_quotes(self):
        raw = {
            "datetime": "2020-01-01T04:00:00Z",
            "bid": 123., "ask": float("inf"),
        }
        record = self.snapshot(raw, data_type="ticker")
        raw["bid"] = -1
        self.assertEqual(123., record["values"]["bid"])
        self.assertIsNone(record["values"]["ask"])
        future = self.snapshot(
            raw, data_type="ticker", as_of="2020-01-01T03:59:00Z",
        )
        self.assertEqual({}, future["values"])
        self.assertIsNone(future["source_timestamp"])
