"""
IPython magic commands for running backtests directly in Jupyter notebooks.

Usage:
    # Load the extension
    %load_ext investing_algorithm_framework

    # Cell magic — define and run a backtest inline
    %%backtest --start 2023-01-01 --end 2023-12-31 --initial-amount 10000 -o results
    from investing_algorithm_framework import TradingStrategy, DataSource

    class MyStrategy(TradingStrategy):
        time_unit = "DAY"
        interval = 1
        data_sources = [
            DataSource(
                identifier="btc",
                symbol="BTC/EUR",
                data_type="OHLCV",
                time_frame="1d",
            )
        ]

        def run_strategy(self, context, data):
            ...

    # Line magic — run a strategy from an existing file
    %backtest strategies/my_strategy.py --start 2023-01-01 --end 2023-12-31 -o results
"""

import argparse
import os
import shlex
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from IPython.core.magic import (
    Magics,
    magics_class,
    cell_magic,
    line_magic,
)


def _build_parser():
    """Build the argument parser for the backtest magic."""
    parser = argparse.ArgumentParser(
        prog="%%backtest",
        description="Run a backtest from a Jupyter notebook cell.",
        add_help=False,
    )
    parser.add_argument(
        "strategy_path",
        nargs="?",
        default=None,
        help="Path to a .py file containing a TradingStrategy subclass "
        "(line magic only).",
    )
    parser.add_argument(
        "--start",
        required=True,
        help="Backtest start date (YYYY-MM-DD or YYYY-MM-DD-HH).",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Backtest end date (YYYY-MM-DD or YYYY-MM-DD-HH). "
        "Defaults to now.",
    )
    parser.add_argument(
        "--initial-amount",
        type=float,
        default=1000.0,
        help="Initial portfolio balance (default: 1000).",
    )
    parser.add_argument(
        "--market",
        default=None,
        help="Market identifier (e.g. BITVAVO, COINBASE).",
    )
    parser.add_argument(
        "--trading-symbol",
        default=None,
        help="Trading / quote currency (e.g. EUR, USD).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Variable name to store the Backtest result in the "
        "notebook namespace.",
    )
    parser.add_argument(
        "--vectorized",
        action="store_true",
        default=False,
        help="Use vectorized backtesting (run_vector_backtest) instead "
        "of event-driven.",
    )
    parser.add_argument(
        "--show-progress",
        action="store_true",
        default=False,
        help="Show progress bars during the backtest.",
    )
    parser.add_argument(
        "--show-report",
        action="store_true",
        default=False,
        help="Display an inline HTML report after the backtest completes.",
    )
    parser.add_argument(
        "--resource-dir",
        default=None,
        help="Resource directory path. Defaults to ./resources.",
    )
    parser.add_argument(
        "--risk-free-rate",
        type=float,
        default=None,
        help="Risk-free rate for metrics calculation.",
    )
    parser.add_argument(
        "--snapshot-interval",
        default="DAILY",
        help="Snapshot interval (DAILY, TRADE_CLOSE). Default: DAILY.",
    )
    parser.add_argument(
        "--fill-missing-data",
        action="store_true",
        default=True,
        help="Fill missing time-series entries (default: True).",
    )
    parser.add_argument(
        "--no-fill-missing-data",
        action="store_true",
        default=False,
        help="Do not fill missing time-series entries.",
    )
    return parser


def _parse_date(value):
    """Parse a date string into a timezone-aware datetime (UTC)."""
    for fmt in ("%Y-%m-%d-%H", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            # Round to the nearest hour as required by BacktestDateRange
            return dt.replace(
                minute=0, second=0, microsecond=0, tzinfo=timezone.utc
            )
        except ValueError:
            continue
    raise ValueError(
        f"Cannot parse date '{value}'. "
        "Expected format: YYYY-MM-DD or YYYY-MM-DD-HH."
    )


def _find_strategy_classes(namespace):
    """Find all TradingStrategy subclasses in a namespace dict."""
    from investing_algorithm_framework.app.strategy import TradingStrategy

    strategies = []

    for obj in namespace.values():
        try:
            if (
                isinstance(obj, type)
                and issubclass(obj, TradingStrategy)
                and obj is not TradingStrategy
            ):
                strategies.append(obj)
        except TypeError:
            continue

    return strategies


def _find_strategy_classes_from_file(file_path):
    """Import a .py file and return all TradingStrategy subclasses in it."""
    import importlib.util

    path = Path(file_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Strategy file not found: {path}")

    spec = importlib.util.spec_from_file_location(
        f"_backtest_magic_{path.stem}", str(path)
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return _find_strategy_classes(vars(module))


def _run_backtest(args, strategies):
    """Execute the backtest using the framework's App API."""
    from investing_algorithm_framework.create_app import create_app
    from investing_algorithm_framework.domain import (
        BacktestDateRange,
        PortfolioConfiguration,
        SnapshotInterval,
        RESOURCE_DIRECTORY,
    )

    start_date = _parse_date(args.start)
    end_date = (
        _parse_date(args.end) if args.end else
        datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
    )

    backtest_date_range = BacktestDateRange(
        start_date=start_date, end_date=end_date
    )

    snapshot_interval = SnapshotInterval.from_value(args.snapshot_interval)
    fill_missing = not args.no_fill_missing_data

    resource_dir = args.resource_dir or os.path.join(
        os.getcwd(), "resources"
    )

    config = {RESOURCE_DIRECTORY: resource_dir}
    app = create_app(config=config)

    # Configure portfolio if market info is provided
    if args.market and args.trading_symbol:
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                initial_balance=args.initial_amount,
                market=args.market,
                trading_symbol=args.trading_symbol,
            )
        )

    if len(strategies) == 0:
        raise RuntimeError(
            "No TradingStrategy subclass found. "
            "Define a class that inherits from TradingStrategy "
            "in your cell or strategy file."
        )

    # Use the first strategy found
    strategy_cls = strategies[0]
    strategy = strategy_cls()

    # Determine market/trading_symbol from strategy if not from CLI
    market = args.market
    trading_symbol = args.trading_symbol

    if args.vectorized:
        backtest = app.run_vector_backtest(
            strategy=strategy,
            backtest_date_range=backtest_date_range,
            initial_amount=args.initial_amount,
            market=market,
            trading_symbol=trading_symbol,
            snapshot_interval=snapshot_interval,
            risk_free_rate=args.risk_free_rate,
            show_progress=args.show_progress,
            fill_missing_data=fill_missing,
        )
    else:
        backtest = app.run_backtest(
            strategy=strategy,
            backtest_date_range=backtest_date_range,
            initial_amount=args.initial_amount,
            market=market,
            trading_symbol=trading_symbol,
            snapshot_interval=snapshot_interval,
            risk_free_rate=args.risk_free_rate,
            show_progress=args.show_progress,
            fill_missing_data=fill_missing,
        )

    return backtest


@magics_class
class BacktestMagics(Magics):
    """IPython magic commands for the investing-algorithm-framework."""

    @cell_magic
    def backtest(self, line, cell):
        """
        %%backtest — define a strategy inline and run a backtest.

        Example::

            %%backtest --start 2023-01-01 --end 2023-12-31 \\
                --initial-amount 10000 --market BITVAVO \\
                --trading-symbol EUR -o results

            from investing_algorithm_framework import (
                TradingStrategy, DataSource, TimeUnit
            )

            class MyStrategy(TradingStrategy):
                time_unit = TimeUnit.DAY
                interval = 1
                data_sources = [
                    DataSource(
                        identifier="btc",
                        symbol="BTC/EUR",
                        data_type="OHLCV",
                        time_frame="1d",
                    )
                ]

                def run_strategy(self, context, data):
                    ...
        """
        parser = _build_parser()

        try:
            args = parser.parse_args(shlex.split(line))
        except SystemExit:
            return

        # Execute the cell code in a fresh namespace that inherits
        # from the user's notebook namespace so imports are available
        cell_ns = dict(self.shell.user_ns)
        exec(compile(cell, "<%%backtest>", "exec"), cell_ns)  # noqa: S102

        strategies = _find_strategy_classes(cell_ns)
        backtest = _run_backtest(args, strategies)

        if args.show_report:
            self._show_report(backtest)

        if args.output:
            self.shell.user_ns[args.output] = backtest
            print(f"Backtest result stored in '{args.output}'")
        else:
            return backtest

    @line_magic
    def backtest(self, line):  # noqa: F811
        """
        %backtest — run a backtest from an existing strategy file.

        Example::

            %backtest strategies/my_strategy.py \\
                --start 2023-01-01 --end 2023-12-31 -o results
        """
        parser = _build_parser()

        try:
            args = parser.parse_args(shlex.split(line))
        except SystemExit:
            return

        if args.strategy_path is None:
            print(
                "Usage: %backtest <strategy_file.py> "
                "--start YYYY-MM-DD [options]"
            )
            return

        strategies = _find_strategy_classes_from_file(args.strategy_path)
        backtest = _run_backtest(args, strategies)

        if args.show_report:
            self._show_report(backtest)

        if args.output:
            self.shell.user_ns[args.output] = backtest
            print(f"Backtest result stored in '{args.output}'")
        else:
            return backtest

    @staticmethod
    def _show_report(backtest):
        """Display an inline HTML report in the notebook."""
        try:
            from investing_algorithm_framework.app.reporting import (
                BacktestReport,
            )

            report = BacktestReport(backtests=[backtest])
            report.show()
        except Exception as e:
            print(f"Could not display report: {e}")


def load_ipython_extension(ipython):
    """
    Entry point called by ``%load_ext investing_algorithm_framework``.

    Registers the ``%backtest`` / ``%%backtest`` magic commands.
    """
    ipython.register_magics(BacktestMagics)
