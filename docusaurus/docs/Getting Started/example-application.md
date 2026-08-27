---
sidebar_position: 2
---

# Example Application

Get started with a complete working example of a trading bot
using the Investing Algorithm Framework.

## Overview

This example demonstrates how to create a sophisticated quantitative trading algorithm. It showcases an RSI-EMA crossover strategy with comprehensive risk management, backtesting capabilities, and professional-grade features. The goal here is to show various capabilities of the framework so you can use this example in your own research.

## Complete Example

> This example uses the `pyindicators` library for technical indicators.
> Make sure to install it via pip:```pip install pyindicators```

The code snippet below shows an algorithm that can be run in two modes:

- **Paper trading** (`--mode paper`): runs `run_paper_trading_live()`,
  which starts the live event loop against real-time market data with
  a simulated (paper) portfolio — useful for validating a strategy
  without risking real capital. Pass `--web` to also expose the REST
  API for monitoring and control.
- **Event backtesting** (`--mode backtest`, the default): runs
  `run_backtest()`, which replays historical OHLCV data through the
  same strategy and produces an HTML performance report
  (`backtest_report.html`) — useful for evaluating a strategy's
  historical performance before risking any capital, paper or real.


```python
import logging.config
from typing import Dict, Any, Union, List
from datetime import datetime, timezone

import pandas as pd
from pyindicators import ema, rsi, crossover, crossunder

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, PositionSize, create_app, RESOURCE_DIRECTORY, \
    BacktestDateRange, BacktestReport, TakeProfitRule, StopLossRule, \
    SignalSide, signals_from_column, DEFAULT_LOGGING_CONFIG, Schedule, Study, \
    Universe, BacktestWindow, PaperTradingMode, ScoreCard, ScoreCardEntry, \
    ExposureRule, ScalingRule, CooldownRule, DATETIME_FORMAT, TIMEZONE


# I'm in Amsterdam — log timestamps in local (CET/CEST) time, Dutch date order.
LOCAL_APP_CONFIG = {
    DATETIME_FORMAT: "%d-%m-%Y %H:%M:%S",
    TIMEZONE: "Europe/Amsterdam",
}

# Anchors the 2-hour schedule to fixed UTC clock boundaries (00:00,
# 02:00, 04:00, ...) so it always runs at the same times regardless of
# when the app starts, and a manual/forced run never shifts the next
# natural run.
SCHEDULE_ANCHOR = datetime(2024, 1, 1, tzinfo=timezone.utc)


# Use the framework provided logging configuration for better debugging and monitoring
logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)
logger = logging.getLogger("investing_algorithm_framework")


class RSIEMACrossoverStrategy(TradingStrategy):
    strategy_id = "RSI-EMA-Crossover-Strategy"
    # Never invest more than 80% of the portfolio at once, across all
    # symbols combined — keeps a cash buffer regardless of how many
    # symbols signal an entry on the same tick.
    exposure_rule = ExposureRule(max_portfolio_percentage=80.0)

    def __init__(
        self,
        schedule: Schedule,
        rsi_time_frame: str,
        rsi_period: int,
        rsi_overbought_threshold,
        rsi_oversold_threshold,
        ema_time_frame,
        ema_short_period,
        ema_long_period,
        ema_cross_lookback_window: int = 10,
        symbols: List[str] = None,
        data_sources=None,
        exposure_rule=None,
        scaling_rules=None,
        cooldowns=None,
    ):
        self.rsi_time_frame = rsi_time_frame
        self.rsi_period = rsi_period
        self.rsi_result_column = f"rsi_{self.rsi_period}"
        self.rsi_overbought_threshold = rsi_overbought_threshold
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.ema_time_frame = ema_time_frame
        self.ema_short_result_column = f"ema_{ema_short_period}"
        self.ema_long_result_column = f"ema_{ema_long_period}"
        self.ema_crossunder_result_column = "ema_crossunder"
        self.ema_crossover_result_column = "ema_crossover"
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.ema_cross_lookback_window = ema_cross_lookback_window

        super().__init__(
            data_sources=data_sources, 
            schedule=schedule, 
            symbols=symbols,
            exposure_rule=exposure_rule, 
            scaling_rules=scaling_rules,
            cooldowns=cooldowns,
        )

    def get_take_profit_rule(self, symbol: str, side: str = None) -> Union[TakeProfitRule, None]:
        return TakeProfitRule(
            symbol=symbol,
            percentage_threshold=10,
            trailing=True,
            sell_percentage=100
        )

    def get_position_size(self, symbol: str) -> Union[PositionSize, None]:
        return PositionSize(
            symbol=symbol,
            percentage_of_portfolio=20.0
        )

    def _prepare_indicators(
        self,
        rsi_data,
        ema_data
    ):
        """
        Helper function to prepare the indicators
        for the strategy. The indicators are calculated
        using the pyindicators library: https://github.com/coding-kitties/PyIndicators
        """
        ema_data = ema(
            ema_data,
            period=self.ema_short_period,
            source_column="Close",
            result_column=self.ema_short_result_column
        )
        ema_data = ema(
            ema_data,
            period=self.ema_long_period,
            source_column="Close",
            result_column=self.ema_long_result_column
        )
        # Detect crossover (short EMA crosses above long EMA)
        ema_data = crossover(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossover_result_column
        )
        # Detect crossunder (short EMA crosses below long EMA)
        ema_data = crossunder(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossunder_result_column
        )
        rsi_data = rsi(
            rsi_data,
            period=self.rsi_period,
            source_column="Close",
            result_column=self.rsi_result_column
        )

        return ema_data, rsi_data

    @staticmethod
    def _scalar(value):
        """Coerce a pandas/numpy scalar to a JSON-safe Python scalar
        (``ScoreCardEntry`` rejects numpy dtypes and NaN)."""
        if value is None:
            return None
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, float):
            if pd.isna(value):
                return None
            return round(value, 6)
        return value

    def _build_score_card(self, side, ema_data, rsi_data) -> ScoreCard:
        """Explain a signal with the exact RSI/EMA readings that
        produced it at the latest bar, so anyone looking at
        ``RunReport.signals`` can see why without re-running the
        strategy.
        """
        latest_ema = ema_data.iloc[-1]
        latest_rsi = rsi_data.iloc[-1]
        rsi_value = self._scalar(latest_rsi.get(self.rsi_result_column))
        ema_short = self._scalar(
            latest_ema.get(self.ema_short_result_column)
        )
        ema_long = self._scalar(latest_ema.get(self.ema_long_result_column))
        entries = [
            ScoreCardEntry("rsi_data_length", len(rsi_data), group="data"),
            ScoreCardEntry("ema_data_length", len(ema_data), group="data"),
            ScoreCardEntry("rsi", rsi_value, group="momentum"),
            ScoreCardEntry(
                "rsi_overbought_threshold", self.rsi_overbought_threshold,
                group="momentum",
            ),
            ScoreCardEntry(
                "rsi_oversold_threshold", self.rsi_oversold_threshold,
                group="momentum",
            ),
            ScoreCardEntry(
                self.ema_short_result_column, ema_short, group="trend"
            ),
            ScoreCardEntry(
                self.ema_long_result_column, ema_long, group="trend"
            ),
            ScoreCardEntry(
                self.ema_crossover_result_column,
                self._scalar(
                    latest_ema.get(self.ema_crossover_result_column)
                ),
                group="trend",
            ),
            ScoreCardEntry(
                self.ema_crossunder_result_column,
                self._scalar(
                    latest_ema.get(self.ema_crossunder_result_column)
                ),
                group="trend",
            ),
        ]

        summaries = {
            SignalSide.OPEN_LONG: (
                f"RSI oversold (<{self.rsi_oversold_threshold}) confirmed "
                f"by an EMA crossover within "
                f"{self.ema_cross_lookback_window} bars"
            ),
            SignalSide.CLOSE_LONG: (
                f"RSI overbought (>={self.rsi_overbought_threshold}) "
                f"confirmed by an EMA crossunder within "
                f"{self.ema_cross_lookback_window} bars"
            ),
        }

        if side is None:
            # No signal fired this tick: explain why not, so the
            # RunReport shows the reasoning even for a no-op tick.
            if rsi_value is not None and rsi_value < self.rsi_oversold_threshold:
                summary = (
                    f"RSI oversold (<{self.rsi_oversold_threshold}) but no "
                    f"EMA crossover within "
                    f"{self.ema_cross_lookback_window} bars — waiting for "
                    f"confirmation"
                )
            elif (
                rsi_value is not None
                and rsi_value >= self.rsi_overbought_threshold
            ):
                summary = (
                    f"RSI overbought (>={self.rsi_overbought_threshold}) "
                    f"but no EMA crossunder within "
                    f"{self.ema_cross_lookback_window} bars — waiting for "
                    f"confirmation"
                )
            else:
                summary = (
                    f"RSI neutral ({self.rsi_oversold_threshold}-"
                    f"{self.rsi_overbought_threshold} range) — no signal"
                )
            return ScoreCard(entries=entries, summary=summary)

        return ScoreCard(entries=entries, summary=summaries.get(side))

    def generate_signals(self, context, data: Dict[str, Any]):
        """
        Generate buy/sell signals per symbol based on the RSI level
        and a recent EMA crossover/crossunder confirmation.

        Args:
            context: Strategy context (portfolio, positions, orders).
            data (Dict[str, Any]): Dictionary containing all the data for
                the strategy data sources.

        Yields:
            Signal: Zero or more OPEN_LONG / CLOSE_LONG signals.
        """
        for symbol in self.symbols:
            ema_data_identifier = f"{symbol}_ema_data"
            rsi_data_identifier = f"{symbol}_rsi_data"
            ema_data, rsi_data = self._prepare_indicators(
                data[ema_data_identifier].copy(),
                data[rsi_data_identifier].copy()
            )

            # crossover confirmed
            ema_crossover_lookback = ema_data[
                self.ema_crossover_result_column].rolling(
                window=self.ema_cross_lookback_window
            ).max().astype(bool)
            # crossunder confirmed
            ema_crossunder_lookback = ema_data[
                self.ema_crossunder_result_column].rolling(
                window=self.ema_cross_lookback_window
            ).max().astype(bool)

            # use only RSI column
            rsi_oversold = rsi_data[self.rsi_result_column] \
                < self.rsi_oversold_threshold
            rsi_overbought = rsi_data[self.rsi_result_column] \
                >= self.rsi_overbought_threshold

            rsi_data["buy_signal"] = (
                rsi_oversold & ema_crossover_lookback
            ).fillna(False).astype(bool)
            rsi_data["sell_signal"] = (
                rsi_overbought & ema_crossunder_lookback
            ).fillna(False).astype(bool)

            yield from (
                signal.with_score_card(
                    self._build_score_card(
                        SignalSide.OPEN_LONG, ema_data, rsi_data
                    )
                )
                for signal in signals_from_column(
                    rsi_data, "buy_signal",
                    side=SignalSide.OPEN_LONG, symbol=symbol,
                )
            )
            yield from (
                signal.with_score_card(
                    self._build_score_card(
                        SignalSide.CLOSE_LONG, ema_data, rsi_data
                    )
                )
                for signal in signals_from_column(
                    rsi_data, "sell_signal",
                    side=SignalSide.CLOSE_LONG, symbol=symbol,
                )
            )

            # No buy/sell signal fired for this symbol on the latest
            # bar: still record a score card so RunReport can explain
            # why, instead of just being silent.
            if not (
                bool(rsi_data["buy_signal"].iloc[-1])
                or bool(rsi_data["sell_signal"].iloc[-1])
            ):
                self.record_score_card(
                    self._build_score_card(None, ema_data, rsi_data),
                    symbol=symbol,
                )

def build_data_sources(
    market, 
    symbols, 
    rsi_time_frame, 
    ema_time_frame, 
    warmup_window=800
):
    """Build the OHLCV data sources for a given market/symbol set.

    Kept outside the strategy so the market used here is always the
    same value passed to ``app.add_market()`` and ``Study.universe``,
    instead of the strategy silently picking its own.
    """
    data_sources = []

    for symbol in symbols:
        full_symbol = f"{symbol}/EUR"
        data_sources.append(
            DataSource(
                identifier=f"{symbol}_rsi_data",
                data_type=DataType.OHLCV,
                time_frame=rsi_time_frame,
                market=market,
                symbol=full_symbol,
                pandas=True,
                warmup_window=warmup_window
            )
        )
        data_sources.append(
            DataSource(
                identifier=f"{symbol}_ema_data",
                data_type=DataType.OHLCV,
                time_frame=ema_time_frame,
                market=market,
                symbol=full_symbol,
                pandas=True,
                warmup_window=800
            )
        )

    return data_sources

def run_backtest(
    market, trading_symbol, rsi_time_frame, ema_time_frame,
    symbols=None, initial_balance=1000,
    exposure_rule=None, scaling_rules=None, cooldowns=None,
):
    """
    Run an event backtest for the RSI-EMA Crossover Strategy.

    Keep in mind that this is an event backtest, because currently 
    the strategy has not implemented the ``generate_signal_series()`` method, 
    which would allow for a vectorized backtest.

    Args:
        market (str): The market to run the backtest on (e.g., "bitvavo").
        trading_symbol (str): The trading symbol to use (e.g., "EUR").
        rsi_time_frame (str): The time frame for the RSI indicator.
        ema_time_frame (str): The time frame for the EMA indicator.
        symbols (list[str]): The symbols to trade (defaults to ["BTC"]).
        initial_balance (float): The starting portfolio balance.
        exposure_rule (ExposureRule): Portfolio-wide max exposure cap.
        scaling_rules (list[ScalingRule]): Per-symbol pyramiding rules.
        cooldowns (list[CooldownRule]): Signal-throttling rules.

    Returns:
        None. Writes the backtest report to an HTML file.
    """
    symbols = symbols if symbols is not None else ["BTC"]
    app = create_app(config=LOCAL_APP_CONFIG)
    strategy = RSIEMACrossoverStrategy(
        schedule=Schedule.every(2, TimeUnit.HOUR, anchor=SCHEDULE_ANCHOR),
        rsi_time_frame=rsi_time_frame,
        rsi_period=14,
        rsi_overbought_threshold=70,
        rsi_oversold_threshold=30,
        ema_time_frame=ema_time_frame,
        ema_short_period=12,
        ema_long_period=26,
        ema_cross_lookback_window=10,
        symbols=symbols,
        data_sources=build_data_sources(
            market=market,
            symbols=symbols,
            rsi_time_frame=rsi_time_frame,
            ema_time_frame=ema_time_frame
        ),
        exposure_rule=exposure_rule,
        scaling_rules=scaling_rules,
        cooldowns=cooldowns,
    )
    app.add_strategy(strategy)
    app.add_market(
        market=market,
        trading_symbol=trading_symbol,
        initial_balance=initial_balance,
    )
    backtest_range = BacktestDateRange(
        start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 6, 1, tzinfo=timezone.utc)
    )
    study = Study(
        name="Test-Study",
        description="Study for the RSI-EMA Crossover Strategy",
        universe=Universe(market=market, trading_symbol=trading_symbol),
        backtest_windows=[BacktestWindow(name="test_window", train_range=backtest_range)],
        initial_capital=initial_balance,
    )
    backtests = app.run_backtest(strategy=strategy, study=study)
    report = BacktestReport(backtests[0])
    report_path = "backtest_report.html"
    report.save(report_path)
    print(f"Backtest report written to: {report_path}")


def run_paper_trading_live(
    market, 
    trading_symbol, 
    rsi_time_frame, 
    ema_time_frame,
    symbols=None,
    initial_balance=1000,
    paper_trading_mode=PaperTradingMode.AUTO,
    web=True, # Enable REST API for monitoring and control
    exposure_rule=None, scaling_rules=None, cooldowns=None,
):
    """
    Run the RSI-EMA Crossover Strategy in paper trading mode.

    Args:
        market (str): The market to run the strategy on (e.g., "bitvavo").
        trading_symbol (str): The trading symbol to use (e.g., "EUR").
        rsi_time_frame (str): The time frame for the RSI indicator.
        ema_time_frame (str): The time frame for the EMA indicator.
        symbols (list[str]): The symbols to trade (defaults to ["BTC"]).
        initial_balance (float): The starting (paper) portfolio balance.
        paper_trading_mode (PaperTradingMode): AUTO, BROKER or LOCAL.
        web (bool): If True, also expose the REST API.
        exposure_rule (ExposureRule): Portfolio-wide max exposure cap.
        scaling_rules (list[ScalingRule]): Per-symbol pyramiding rules.
        cooldowns (list[CooldownRule]): Signal-throttling rules.
    """
    symbols = symbols if symbols is not None else ["BTC"]
    app = create_app(config=LOCAL_APP_CONFIG, web=web)
    strategy = RSIEMACrossoverStrategy(
        schedule=Schedule.every(2, TimeUnit.HOUR, anchor=SCHEDULE_ANCHOR),
        rsi_time_frame=rsi_time_frame,
        rsi_period=14,
        rsi_overbought_threshold=70,
        rsi_oversold_threshold=30,
        ema_time_frame=ema_time_frame,
        ema_short_period=12,
        ema_long_period=26,
        ema_cross_lookback_window=10,
        symbols=symbols,
        data_sources=build_data_sources(
            market=market,
            symbols=symbols,
            rsi_time_frame=rsi_time_frame,
            ema_time_frame=ema_time_frame
        ),
        exposure_rule=exposure_rule,
        scaling_rules=scaling_rules,
        cooldowns=cooldowns,
    )
    app.add_strategy(strategy)
    app.add_market(
        market=market,
        trading_symbol=trading_symbol,
        initial_balance=initial_balance,
        paper_trading=True,
        paper_trading_mode=paper_trading_mode,
    )
    app.run(run_immediately_on_start=True)  # Start the event loop and run the algorithm immediately

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="RSI-EMA Crossover Strategy runner"
    )
    parser.add_argument(
        "--mode", choices=["backtest", "paper"], default="backtest",
        help="Run an event backtest or paper trading live (default: backtest)"
    )
    parser.add_argument("--market", default="bitvavo")
    parser.add_argument("--trading-symbol", default="EUR")
    parser.add_argument("--symbols", nargs="+", default=["BTC"])
    parser.add_argument("--rsi-time-frame", default="2h")
    parser.add_argument("--ema-time-frame", default="2h")
    parser.add_argument("--initial-balance", type=float, default=1000)
    parser.add_argument(
        "--paper-trading-mode", choices=["auto", "broker", "local"],
        default="auto",
        help="Only used when --mode paper (default: auto)"
    )
    parser.add_argument(
        "--web", 
        action="store_true",
        help="Also expose the REST API (only used when --mode paper)",
        default=True
    )
    args = parser.parse_args()

    # Risk rules for the strategies. exposure_rule is portfolio-wide
    # (one instance). scaling_rules/cooldowns support a symbol=None
    # default entry that applies to any symbol without its own
    # symbol-specific override. Position sizing and take profit are
    # already handled dynamically per-symbol by the strategy's
    # get_position_size()/get_take_profit_rule() methods.
    exposure_rule = ExposureRule(max_portfolio_percentage=80.0)
    scaling_rules = [ScalingRule(max_position_percentage=20.0)]  # portfolio-wide, any side and symbol
    cooldowns = [CooldownRule(bars=5)]  # portfolio-wide, any side and symbol

    # Use Amsterdam timezone for consistent backtest results, as Bitvavo uses CET/CEST
    # amsterdam_tz = timezone(timedelta(hours=2))  # CEST is UTC+2

    if args.mode == "backtest":
        run_backtest(
            market=args.market,
            trading_symbol=args.trading_symbol,
            symbols=args.symbols,
            rsi_time_frame=args.rsi_time_frame,
            ema_time_frame=args.ema_time_frame,
            initial_balance=args.initial_balance,
            exposure_rule=exposure_rule,
            scaling_rules=scaling_rules,
            cooldowns=cooldowns,
        )
    else:
        run_paper_trading_live(
            market=args.market,
            trading_symbol=args.trading_symbol,
            symbols=args.symbols,
            rsi_time_frame=args.rsi_time_frame,
            ema_time_frame=args.ema_time_frame,
            initial_balance=args.initial_balance,
            paper_trading_mode=PaperTradingMode(args.paper_trading_mode),
            web=args.web,
            exposure_rule=exposure_rule,
            scaling_rules=scaling_rules,
            cooldowns=cooldowns,
        ) 
```

## Code Breakdown

Let's break down each part of this example:

### 1. Imports and Setup

```python
from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, PositionSize, create_app, \
    BacktestDateRange, BacktestReport, TakeProfitRule, StopLossRule, \
    SignalSide, signals_from_column, ExposureRule, \
    DEFAULT_LOGGING_CONFIG
```

- **pyindicators**: Technical analysis library for RSI and EMA calculations
- **Framework imports**: Core classes for strategy development, backtesting, and risk management

### 2. Logging Configuration

```python
logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)
```

- Sets up logging using the framework's default configuration for better debugging and monitoring

### 3. Strategy configuration

`RSIEMACrossoverStrategy` configures its position sizing and risk
rules two different ways, depending on whether the value is the same
for every instance or needs to vary per call site:

- **Static, one-per-strategy objects** — `exposure_rule`,
  `scaling_rules`, and `cooldowns` are constructed *once* and handed
  to `super().__init__()` in the constructor. `exposure_rule` is also
  set as a class attribute with a sensible default (80% max exposure),
  so it still applies even if a caller doesn't pass one explicitly;
  `scaling_rules`/`cooldowns` default to `None` and are left disabled
  unless the caller supplies them (see the CLI entrypoint in §7,
  which builds all three and passes them into every instance).
- **Dynamic, per-symbol callbacks** — `get_position_size()` and
  `get_take_profit_rule()` are overridden methods, not constructor
  arguments. The framework calls them with the specific `symbol` a
  signal just fired for, so the sizing/exit logic can vary by symbol
  or even by market conditions instead of being fixed at construction
  time. Here both are constant (20% position size, 10% trailing take
  profit) for every symbol, but they could just as easily look up a
  volatility measure per symbol and size accordingly.

```python
class RSIEMACrossoverStrategy(TradingStrategy):
    strategy_id = "RSI-EMA-Crossover-Strategy"
    # Never invest more than 80% of the portfolio at once, across all
    # symbols combined — keeps a cash buffer regardless of how many
    # symbols signal an entry on the same tick.
    exposure_rule = ExposureRule(max_portfolio_percentage=80.0)

    def __init__(
        self,
        schedule: Schedule,
        rsi_time_frame: str,
        rsi_period: int,
        rsi_overbought_threshold,
        rsi_oversold_threshold,
        ema_time_frame,
        ema_short_period,
        ema_long_period,
        ema_cross_lookback_window: int = 10,
        symbols: List[str] = None,
        data_sources=None,
        exposure_rule=None,
        scaling_rules=None,
        cooldowns=None,
    ):
        self.rsi_time_frame = rsi_time_frame
        self.rsi_period = rsi_period
        self.rsi_result_column = f"rsi_{self.rsi_period}"
        self.rsi_overbought_threshold = rsi_overbought_threshold
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.ema_time_frame = ema_time_frame
        self.ema_short_result_column = f"ema_{ema_short_period}"
        self.ema_long_result_column = f"ema_{ema_long_period}"
        self.ema_crossunder_result_column = "ema_crossunder"
        self.ema_crossover_result_column = "ema_crossover"
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.ema_cross_lookback_window = ema_cross_lookback_window

        super().__init__(
            data_sources=data_sources, 
            schedule=schedule, 
            symbols=symbols,
            exposure_rule=exposure_rule, 
            scaling_rules=scaling_rules,
            cooldowns=cooldowns,
        )

    def get_take_profit_rule(self, symbol: str, side: str = None) -> Union[TakeProfitRule, None]:
        return TakeProfitRule(
            symbol=symbol,
            percentage_threshold=10,
            trailing=True,
            sell_percentage=100
        )

    def get_position_size(self, symbol: str) -> Union[PositionSize, None]:
        return PositionSize(
            symbol=symbol,
            percentage_of_portfolio=20.0
        )
```

And the risk rules built once in the CLI entrypoint (see §7) and
passed into every strategy instance:

```python
exposure_rule = ExposureRule(max_portfolio_percentage=80.0)
scaling_rules = [ScalingRule(max_position_percentage=20.0)]
cooldowns = [CooldownRule(bars=5)]
```

The strategy is built from a **schedule** and five distinct **risk
objects**, each answering a different question:

- **`schedule`** (`Schedule.every(2, TimeUnit.HOUR)`): *when* does the
  strategy run? Passed into the constructor, not hardcoded, so the
  same class could be scheduled differently per instance.
- **`PositionSize`** (`get_position_size()`): *how much* to buy for a
  single entry — here, 20% of the portfolio per symbol.
- **`TakeProfitRule`** (`get_take_profit_rule()`): *when to exit a
  winner* — a 10% trailing take profit that sells 100% of the
  position.
- **`ScalingRule`** (`max_position_percentage=20.0`): *how far a
  single symbol can grow* — caps pyramiding so repeated entries on
  the same symbol can't exceed 20% of the portfolio.
- **`CooldownRule`** (`bars=5`): *how soon can it re-enter* —
  throttles new entries for 5 bars after any signal, portfolio-wide.
- **`ExposureRule`** (`max_portfolio_percentage=80.0`): *how much of
  the whole portfolio can be invested at once* — a cash buffer across
  every symbol combined, regardless of how many individually signal
  an entry on the same tick.

### 4. Data Sources

```python
for symbol in self.symbols:
    full_symbol = f"{symbol}/EUR"
    data_sources.append(
        DataSource(
            identifier=f"{symbol}_rsi_data",
            data_type=DataType.OHLCV,
            time_frame=self.rsi_time_frame,
            market=market,
            symbol=full_symbol,
            pandas=True,
            warmup_window=800
        )
    )
    data_sources.append(
        DataSource(
            identifier=f"{symbol}_ema_data",
            data_type=DataType.OHLCV,
            time_frame=self.ema_time_frame,
            market=market,
            symbol=full_symbol,
            pandas=True,
            warmup_window=800
        )
    )
```

**Data Sources for Technical Analysis:**
- **RSI Data Source**: OHLCV data for RSI indicator calculation
- **EMA Data Source**: OHLCV data for moving average calculations
- **warmup_window**: 800 candles for sufficient historical data
- **pandas**: Returns data as pandas DataFrame for easy analysis

### 5. Technical Indicators

```python
def _prepare_indicators(self, rsi_data, ema_data):
    # Calculate short and long EMAs
    ema_data = ema(ema_data, period=self.ema_short_period,
                   source_column="Close", result_column=self.ema_short_result_column)
    ema_data = ema(ema_data, period=self.ema_long_period,
                   source_column="Close", result_column=self.ema_long_result_column)

    # Detect EMA crossovers
    ema_data = crossover(ema_data, first_column=self.ema_short_result_column,
                        second_column=self.ema_long_result_column,
                        result_column=self.ema_crossover_result_column)

    # Calculate RSI
    rsi_data = rsi(rsi_data, period=self.rsi_period,
                   source_column="Close", result_column=self.rsi_result_column)
```

**Technical Indicators Used:**
- **EMA (Exponential Moving Average)**: Short-term (12) and long-term (26) trends
- **RSI (Relative Strength Index)**: Momentum oscillator (14-period)
- **Crossover Detection**: Identifies when short EMA crosses above/below long EMA

### 6. Strategy Logic

```python
def generate_signals(self, context, data: Dict[str, Any]):
    # Buy when RSI is oversold AND EMA crossover occurred recently
    rsi_oversold = rsi_data[self.rsi_result_column] < self.rsi_oversold_threshold
    ema_crossover_lookback = ema_data[self.ema_crossover_result_column].rolling(
        window=self.ema_cross_lookback_window).max().astype(bool)
    rsi_data["buy_signal"] = (rsi_oversold & ema_crossover_lookback).fillna(False)

    # Sell when RSI is overbought AND EMA crossunder occurred recently
    rsi_overbought = rsi_data[self.rsi_result_column] >= self.rsi_overbought_threshold
    ema_crossunder_lookback = ema_data[self.ema_crossunder_result_column].rolling(
        window=self.ema_cross_lookback_window).max().astype(bool)
    rsi_data["sell_signal"] = (rsi_overbought & ema_crossunder_lookback).fillna(False)

    yield from signals_from_column(
        rsi_data, "buy_signal", side=SignalSide.OPEN_LONG, symbol=symbol,
    )
    yield from signals_from_column(
        rsi_data, "sell_signal", side=SignalSide.CLOSE_LONG, symbol=symbol,
    )
```

**Trading Logic:**
- **Buy Signals**: Generated when RSI indicates oversold conditions (< 30) AND a recent EMA bullish crossover
- **Sell Signals**: Generated when RSI indicates overbought conditions (> 70) AND a recent EMA bearish crossover
- **Confirmation**: Uses lookback window to ensure signals are confirmed over multiple periods

### 7. Application Setup, Backtesting, and Paper Trading

```python
if args.mode == "backtest":
    run_backtest(
        market=args.market,
        trading_symbol=args.trading_symbol,
        symbols=args.symbols,
        rsi_time_frame=args.rsi_time_frame,
        ema_time_frame=args.ema_time_frame,
        initial_balance=args.initial_balance,
        exposure_rule=exposure_rule,
        scaling_rules=scaling_rules,
        cooldowns=cooldowns,
    )
else:
    run_paper_trading_live(
        market=args.market,
        trading_symbol=args.trading_symbol,
        symbols=args.symbols,
        rsi_time_frame=args.rsi_time_frame,
        ema_time_frame=args.ema_time_frame,
        initial_balance=args.initial_balance,
        paper_trading_mode=PaperTradingMode(args.paper_trading_mode),
        web=args.web,
        exposure_rule=exposure_rule,
        scaling_rules=scaling_rules,
        cooldowns=cooldowns,
    )
```

- **`run_backtest(...)`**: creates the app, attaches the strategy and
  the Bitvavo/EUR market, wraps the January 2023 – June 2024 window
  in a `BacktestWindow`/`Study`, and runs `app.run_backtest(strategy=strategy, study=study)`.
  The resulting `BacktestReport` is written to `backtest_report.html`.
- **`run_paper_trading_live(...)`**: creates the app with the same
  strategy and market, this time with `paper_trading=True`, and calls
  `app.run(run_immediately_on_start=True)` to start the live event
  loop against a simulated portfolio. Passing `--web` also exposes
  the REST API for monitoring/control.
- Both paths share the same `RSIEMACrossoverStrategy`,
  `exposure_rule`, `scaling_rules`, and `cooldowns` — only the
  execution mode differs, so a strategy validated in backtest behaves
  identically once switched to paper (or live) trading.

## Running the Example

### Prerequisites

1. **Install the framework** (see [Installation](installation)):
   ```bash
   pip install investing-algorithm-framework
   ```

2. **Install pyindicators** for technical indicators:
   ```bash
   pip install pyindicators
   ```

### Setup

1. **Create a new file** called `rsi_ema_strategy.py` and copy the example code above.

2. **Create a `.env` file** (only needed for `--mode paper` against a
   real exchange account — the default paper-trading simulator works
   without any credentials):
   ```bash
   BITVAVO_API_KEY=your_api_key_here
   BITVAVO_SECRET_KEY=your_api_secret_here
   ```

3. **Run an event backtest** (default mode):
   ```bash
   python rsi_ema_strategy.py --mode backtest
   ```

4. **Or run paper trading live**, optionally with the REST API:
   ```bash
   python rsi_ema_strategy.py --mode paper --web
   ```

   Every argument (`--market`, `--symbols`, `--rsi-time-frame`,
   `--ema-time-frame`, `--initial-balance`, `--paper-trading-mode`,
   ...) has a sensible default, so the script also runs unmodified.

## Key Features Demonstrated

### 1. **Advanced Technical Analysis**
- **Multiple Technical Indicators**: RSI and EMA calculations via `pyindicators`
- **Signal Confirmation**: an EMA crossover/crossunder must occur within a lookback window before an RSI oversold/overbought reading fires a signal
- **Explainable Signals**: `ScoreCard`/`ScoreCardEntry` attach the exact indicator readings behind every signal (and every no-op tick) to the `RunReport`

### 2. **Comprehensive Risk Management**
- **Position Sizing**: `get_position_size()` caps each symbol at 20% of the portfolio
- **Take Profit**: `get_take_profit_rule()` sells with a 10% trailing take profit
- **Scaling & Cooldowns**: `ScalingRule` caps pyramiding per symbol and `CooldownRule` throttles re-entries after a signal
- **Portfolio-Wide Exposure**: `ExposureRule` caps total invested capital at 80% across every symbol combined

### 3. **One Strategy, Two Execution Modes**
- **Event Backtesting**: deterministic, historical replay producing an HTML report — ideal for validating a strategy before risking any capital
- **Paper Trading**: the same strategy run live against real-time data with a simulated portfolio — ideal for a final dry run before going live

### 4. **Production-Ready Structure**
- **Modular Design**: strategy logic, data source construction, and mode-specific run functions are cleanly separated
- **Logging Integration**: the framework's `DEFAULT_LOGGING_CONFIG` for consistent, structured logs
- **Configurable via CLI**: every parameter (market, symbols, timeframes, balance, risk rules) is overridable without touching the code

## Next Steps

Now that you have a working example, you can:

1. **Experiment with parameters** — modify RSI/EMA periods and thresholds, or pass different `--symbols`/`--market` values
2. **Add more symbols** — extend `--symbols` to trade ETH, ADA, and other cryptocurrencies
3. **Go live** — set real `BITVAVO_API_KEY`/`BITVAVO_SECRET_KEY` credentials and switch `paper_trading=False` once you're confident in the strategy
4. **Create custom indicators** — develop your own technical analysis logic in `_prepare_indicators`
5. **Tune the risk rules** — adjust `ExposureRule`, `ScalingRule`, and `CooldownRule` to your risk tolerance

Continue to [Application Setup](application-setup) to learn how to structure more complex trading applications, or jump to [Strategies](strategies) to learn about implementing more trading logic.

## See also

The strategy above generates buy/sell signals one symbol at a time. For
**cross-sectional** strategies — where you score and rank a universe of
symbols against each other (e.g. "long the top-10 by momentum, short
the bottom-10") — see the [Pipelines](../Advanced%20Concepts/pipelines)
guide. Pipelines also enable vectorised backtesting, which is
significantly faster for large universes.

