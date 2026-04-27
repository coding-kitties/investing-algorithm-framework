import os
from unittest import TestCase
from unittest.mock import MagicMock

from investing_algorithm_framework.notebook.magic import (
    _build_parser,
    _parse_date,
    _find_strategy_classes,
    BacktestMagics,
    load_ipython_extension,
)


class TestParseDate(TestCase):

    def test_parse_date_ymd(self):
        dt = _parse_date("2023-06-15")
        self.assertEqual(dt.year, 2023)
        self.assertEqual(dt.month, 6)
        self.assertEqual(dt.day, 15)
        self.assertEqual(dt.hour, 0)
        self.assertIsNotNone(dt.tzinfo)

    def test_parse_date_ymdh(self):
        dt = _parse_date("2023-06-15-14")
        self.assertEqual(dt.hour, 14)
        self.assertEqual(dt.minute, 0)
        self.assertIsNotNone(dt.tzinfo)

    def test_parse_date_invalid(self):
        with self.assertRaises(ValueError):
            _parse_date("not-a-date")

    def test_parse_date_rounds_to_hour(self):
        dt = _parse_date("2023-01-01")
        self.assertEqual(dt.minute, 0)
        self.assertEqual(dt.second, 0)
        self.assertEqual(dt.microsecond, 0)


class TestBuildParser(TestCase):

    def test_minimal_args(self):
        parser = _build_parser()
        args = parser.parse_args(["--start", "2023-01-01"])
        self.assertEqual(args.start, "2023-01-01")
        self.assertIsNone(args.end)
        self.assertEqual(args.initial_amount, 1000.0)
        self.assertIsNone(args.output)
        self.assertFalse(args.vectorized)
        self.assertFalse(args.show_report)

    def test_full_args(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--start", "2023-01-01",
            "--end", "2023-12-31",
            "--initial-amount", "5000",
            "--market", "BITVAVO",
            "--trading-symbol", "EUR",
            "-o", "results",
            "--vectorized",
            "--show-report",
            "--show-progress",
        ])
        self.assertEqual(args.initial_amount, 5000.0)
        self.assertEqual(args.market, "BITVAVO")
        self.assertEqual(args.trading_symbol, "EUR")
        self.assertEqual(args.output, "results")
        self.assertTrue(args.vectorized)
        self.assertTrue(args.show_report)
        self.assertTrue(args.show_progress)

    def test_strategy_path_line_magic(self):
        parser = _build_parser()
        args = parser.parse_args([
            "my_strategy.py", "--start", "2023-01-01"
        ])
        self.assertEqual(args.strategy_path, "my_strategy.py")

    def test_risk_free_rate(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--start", "2023-01-01",
            "--risk-free-rate", "0.04",
        ])
        self.assertEqual(args.risk_free_rate, 0.04)

    def test_no_fill_missing_data(self):
        parser = _build_parser()
        args = parser.parse_args([
            "--start", "2023-01-01",
            "--no-fill-missing-data",
        ])
        self.assertTrue(args.no_fill_missing_data)


class TestFindStrategyClasses(TestCase):

    def test_finds_strategy_subclass(self):
        from investing_algorithm_framework.app.strategy import TradingStrategy

        class DummyStrategy(TradingStrategy):
            time_unit = "DAY"
            interval = 1

        ns = {"DummyStrategy": DummyStrategy, "x": 42, "s": "hello"}
        found = _find_strategy_classes(ns)
        self.assertEqual(len(found), 1)
        self.assertIs(found[0], DummyStrategy)

    def test_finds_multiple_strategies(self):
        from investing_algorithm_framework.app.strategy import TradingStrategy

        class StratA(TradingStrategy):
            time_unit = "DAY"
            interval = 1

        class StratB(TradingStrategy):
            time_unit = "HOUR"
            interval = 4

        ns = {"StratA": StratA, "StratB": StratB}
        found = _find_strategy_classes(ns)
        self.assertEqual(len(found), 2)

    def test_ignores_base_class(self):
        from investing_algorithm_framework.app.strategy import TradingStrategy

        ns = {"TradingStrategy": TradingStrategy}
        found = _find_strategy_classes(ns)
        self.assertEqual(len(found), 0)

    def test_ignores_non_classes(self):
        ns = {"a": 1, "b": "text", "c": [1, 2]}
        found = _find_strategy_classes(ns)
        self.assertEqual(len(found), 0)


class TestLoadExtension(TestCase):

    def test_registers_magics(self):
        mock_ipython = MagicMock()
        load_ipython_extension(mock_ipython)
        mock_ipython.register_magics.assert_called_once_with(BacktestMagics)

    def test_top_level_load_ext(self):
        from investing_algorithm_framework import load_ipython_extension \
            as top_load
        mock_ipython = MagicMock()
        top_load(mock_ipython)
        mock_ipython.register_magics.assert_called_once()
