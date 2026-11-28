# %% Setup: run this cell first in VS Code's Python Interactive Window.
"""Compare a basic RSI/EMA strategy with two multi-indicator strategies.

Run from the repository root with PyIndicators installed::

    python -m examples.charts.layered_equity_chart

The benchmark is ^GSPC, not a dividend-adjusted SPY investment. It uses
native index returns without EUR/USD conversion. Loading prices needs
internet access; displaying the resulting chart does not.

The default backtest uses real BTC/EUR candles downloaded/cached via CCXT.
Each strategy runs independently with EUR 10,000 and a 0.25% fee per fill.
The baseline buys rare oversold rebounds; the advanced profiles combine
EMA trend, MACD momentum,
RSI recovery, Bollinger re-entry and an ATR volatility filter. They illustrate
more frequent, event-based entries, not a guarantee of profitable trading.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import webbrowser

import pandas as pd
from pyindicators import atr, bollinger_bands, ema, macd, rsi

from investing_algorithm_framework import (
    RESOURCE_DIRECTORY,
    BacktestDateRange,
    BacktestEngine,
    BacktestIndex,
    BacktestRunConfiguration,
    BacktestWindow,
    ConfluenceScoreConfig,
    ConfluenceScoringStrategy,
    CooldownRule,
    DataProvider,
    DataSource,
    ExecutionConfig,
    ExposureRule,
    IndicatorConfig,
    IndicatorRule,
    PositionSize,
    Schedule,
    SignalSide,
    StopLossRule,
    Study,
    TakeProfitRule,
    TimeUnit,
    TradingCost,
    Universe,
    create_app,
    create_layered_equity_chart,
    download_v2,
)
from investing_algorithm_framework.app.reporting.charts._finterion_render \
    import render_chart_html


RESOURCE_PATH = Path(__file__).resolve().parent / "resources"
START = datetime(2025, 1, 1, tzinfo=timezone.utc)
BAR = timedelta(hours=2)
WARMUP_BARS = 50
N_BARS = 650
DATE_RANGE = BacktestDateRange(
    start_date=START,
    end_date=START + (N_BARS - WARMUP_BARS - 1) * BAR,
)


class RSIEMAStrategy(ConfluenceScoringStrategy):
    """Comparison baseline: buy rare oversold rebounds above EMA.

    Entry requires RSI < 30 AND Close > EMA. Exit requires RSI >= 70 OR
    Close < EMA. A fixed stop loss and take profit cover the entire trade;
    new positions request 25% of portfolio value. Percentage arguments use
    percentage points (for example, 5 means 5%, not 0.05).
    """
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]

    def __init__(
        self,
        ema_period: int,
        rsi_period: int,
        take_profit_percentage: float,
        stop_loss_percentage: float,
    ):
        self.ema_period = ema_period
        self.rsi_period = rsi_period
        self.take_profit_percentage = take_profit_percentage
        self.stop_loss_percentage = stop_loss_percentage
        warmup = max(ema_period, rsi_period) + 1
        super().__init__(
            algorithm_id=(
                f"EMA{ema_period}-RSI{rsi_period}"
                f"-TP{take_profit_percentage}-SL{stop_loss_percentage}"
            ),
            data_sources=[
                DataSource(
                    identifier="btc_2h",
                    symbol="BTC/EUR",
                    market="BITVAVO",
                    data_type="OHLCV",
                    time_frame="2h",
                    warmup_window=warmup,
                    pandas=True,
                ),
            ],
            indicator_configs=self._create_indicator_configs(),
            confluence_cards=self._create_confluence_cards(),
            position_sizes=[
                PositionSize(symbol="BTC", percentage_of_portfolio=25),
            ],
            stop_losses=[
                StopLossRule(
                    symbol="BTC", percentage_threshold=stop_loss_percentage,
                    sell_percentage=100, trailing=False,
                ),
            ],
            take_profits=[
                TakeProfitRule(
                    symbol="BTC", percentage_threshold=take_profit_percentage,
                    sell_percentage=100, trailing=False,
                ),
            ],
        )
        self.set_parameters({
            "ema_period": ema_period,
            "rsi_period": rsi_period,
            "take_profit_percentage": take_profit_percentage,
            "stop_loss_percentage": stop_loss_percentage,
        })

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Add causal RSI/EMA columns without changing shared candles."""
        data = ema(
            data.copy(), source_column="Close", period=self.ema_period,
            result_column="ema",
        )
        data = rsi(
            data, source_column="Close", period=self.rsi_period,
            result_column="rsi",
        )
        data["ema_distance"] = data["Close"] - data["ema"]
        return data

    def _create_indicator_configs(self) -> list[IndicatorConfig]:
        """Calculate both outputs together using PyIndicators."""
        return [
            IndicatorConfig(
                id="momentum", calculate=self.calculate_indicators,
                data_source="btc_2h", timeframe="2h",
                output_columns=["rsi", "ema_distance"],
                minimum_history=max(self.ema_period, self.rsi_period) + 1,
                execution="precompute",
            ),
        ]

    def _create_confluence_cards(self) -> list[ConfluenceScoreConfig]:
        """Two unit-weight entry confirmations implement AND; exits use OR."""
        return [
            ConfluenceScoreConfig(
                id="long_entry", side=SignalSide.OPEN_LONG, symbols=["BTC"],
                rules={
                    "oversold": IndicatorRule(
                        indicator_id="momentum", output_column="rsi",
                        threshold=30, comparison="lt",
                        group_weights={"primary": 1},
                    ),
                    "above_ema": IndicatorRule(
                        indicator_id="momentum", output_column="ema_distance",
                        threshold=0, comparison="gt",
                        group_weights={"primary": 1},
                    ),
                },
                group_thresholds={"primary": 2},
            ),
            ConfluenceScoreConfig(
                id="long_exit", side=SignalSide.CLOSE_LONG, symbols=["BTC"],
                rules={
                    "overbought": IndicatorRule(
                        indicator_id="momentum", output_column="rsi",
                        threshold=70, comparison="ge",
                        group_weights={"primary": 1},
                    ),
                    "below_ema": IndicatorRule(
                        indicator_id="momentum", output_column="ema_distance",
                        threshold=0, comparison="lt",
                        group_weights={"primary": 1},
                    ),
                },
                group_thresholds={"primary": 1},
            ),
        ]


class TrendPullbackStrategy(ConfluenceScoringStrategy):
    """Long-only trend and recovery entries with independent safety gates.

    Entry requires ALL of these groups:
        trend: fast EMA > slow EMA;
        setup: an EMA bullish turn, MACD histogram bullish turn, RSI recovery
            through the configured level, OR re-entry above the lower
            Bollinger band;
        safety: positive MACD histogram, RSI < 70, AND ATR/Close below the
            configured maximum percentage.

    Setup flags last one candle, rather than buying on every bullish bar.
    Exit requires RSI >= 70 OR negative MACD histogram OR a bearish EMA
    trend. Entry safety conditions make entry and exit signals disjoint.
    A trailing stop, fixed profit target, buy-only cooldown and 50% total
    exposure cap complement signal exits. No shorting is assumed on Bitvavo.

    Faster indicators and smaller profit targets generally turn over more
    often than the baseline, but actual trade counts depend on market data.
    All percentage arguments are percentage points, not fractions.
    """

    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]

    def __init__(
        self,
        fast_ema_period: int = 8,
        slow_ema_period: int = 21,
        rsi_period: int = 14,
        take_profit_percentage: float = 3,
        stop_loss_percentage: float = 2,
        rsi_recovery_level: float = 50,
        max_atr_percentage: float = 4,
        cooldown_bars: int = 3,
    ):
        if not 0 < fast_ema_period < slow_ema_period:
            raise ValueError("EMA periods must satisfy 0 < fast < slow.")
        if not 0 < rsi_recovery_level < 70:
            raise ValueError("RSI recovery level must be between 0 and 70.")
        if max_atr_percentage <= 0:
            raise ValueError("Maximum ATR percentage must be positive.")
        self.fast_ema_period = fast_ema_period
        self.slow_ema_period = slow_ema_period
        self.rsi_period = rsi_period
        self.rsi_recovery_level = rsi_recovery_level
        warmup = max(slow_ema_period, rsi_period + 1, 26 + 9, 20) + 1
        rules = {
            "uptrend": IndicatorRule(
                indicator_id="technical", output_column="ema_spread",
                threshold=0, comparison="gt", group_weights={"trend": 1},
            ),
            "positive_momentum": IndicatorRule(
                indicator_id="technical", output_column="macd_histogram",
                threshold=0, comparison="gt", group_weights={"safety": 1},
            ),
            "not_overbought": IndicatorRule(
                indicator_id="technical", output_column="rsi",
                threshold=70, comparison="lt", group_weights={"safety": 1},
            ),
            "normal_volatility": IndicatorRule(
                indicator_id="technical", output_column="atr_percent",
                threshold=max_atr_percentage, comparison="le",
                group_weights={"safety": 1},
            ),
        }
        rules.update({
            name: IndicatorRule(
                indicator_id="technical", output_column=name,
                threshold=0, comparison="gt", group_weights={"setup": 1},
            )
            for name in (
                "trend_turn", "macd_turn", "rsi_recovery",
                "band_reentry",
            )
        })
        super().__init__(
            algorithm_id=(
                f"Trend-EMA{fast_ema_period}-{slow_ema_period}"
                f"-RSI{rsi_period}-TP{take_profit_percentage}"
                f"-SL{stop_loss_percentage}"
            ),
            data_sources=[
                DataSource(
                    identifier="btc_2h", symbol="BTC/EUR", market="BITVAVO",
                    data_type="OHLCV", time_frame="2h",
                    warmup_window=warmup, pandas=True,
                ),
            ],
            indicator_configs=[
                IndicatorConfig(
                    id="technical", calculate=self.calculate_indicators,
                    data_source="btc_2h", timeframe="2h",
                    output_columns=[
                        "ema_spread", "macd_histogram", "rsi", "atr_percent",
                        "trend_turn", "macd_turn", "rsi_recovery",
                        "band_reentry",
                    ],
                    minimum_history=warmup, execution="precompute",
                ),
            ],
            confluence_cards=[
                ConfluenceScoreConfig(
                    id="long_entry", side=SignalSide.OPEN_LONG,
                    symbols=["BTC"], rules=rules,
                    group_thresholds={"trend": 1, "setup": 1, "safety": 3},
                ),
                ConfluenceScoreConfig(
                    id="long_exit", side=SignalSide.CLOSE_LONG,
                    symbols=["BTC"],
                    rules={
                        name: IndicatorRule(
                            indicator_id="technical", output_column=column,
                            threshold=threshold, comparison=comparison,
                            group_weights={"exit": 1},
                        )
                        for name, column, threshold, comparison in (
                            ("overbought", "rsi", 70, "ge"),
                            ("bearish_momentum", "macd_histogram", 0, "lt"),
                            ("downtrend", "ema_spread", 0, "lt"),
                        )
                    },
                    group_thresholds={"exit": 1},
                ),
            ],
            position_sizes=[
                PositionSize(symbol="BTC", percentage_of_portfolio=25),
            ],
            exposure_rule=ExposureRule(max_portfolio_percentage=50),
            stop_losses=[
                StopLossRule(
                    symbol="BTC", percentage_threshold=stop_loss_percentage,
                    sell_percentage=100, trailing=True,
                ),
            ],
            take_profits=[
                TakeProfitRule(
                    symbol="BTC", percentage_threshold=take_profit_percentage,
                    sell_percentage=100, trailing=False,
                ),
            ],
            cooldowns=[
                CooldownRule(
                    symbol="BTC", trigger="buy", blocks="buy",
                    bars=cooldown_bars,
                ),
            ],
        )
        self.set_parameters({
            "fast_ema_period": fast_ema_period,
            "slow_ema_period": slow_ema_period,
            "rsi_period": rsi_period,
            "take_profit_percentage": take_profit_percentage,
            "stop_loss_percentage": stop_loss_percentage,
            "rsi_recovery_level": rsi_recovery_level,
            "max_atr_percentage": max_atr_percentage,
            "cooldown_bars": cooldown_bars,
        })

    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Compute trailing indicators and causal one-bar crossings."""
        data = ema(
            data.copy(), source_column="Close", period=self.fast_ema_period,
            result_column="ema_fast",
        )
        data = ema(
            data, source_column="Close", period=self.slow_ema_period,
            result_column="ema_slow",
        )
        data = rsi(data, source_column="Close", period=self.rsi_period)
        data = macd(data, source_column="Close")
        data = bollinger_bands(data, source_column="Close", period=20)
        data = atr(data, source_column="Close", period=14, result_column="atr")
        data["ema_spread"] = data["ema_fast"] - data["ema_slow"]
        data["atr_percent"] = 100 * data["atr"] / data["Close"]
        for output, column, threshold in (
            ("trend_turn", "ema_spread", 0),
            ("macd_turn", "macd_histogram", 0),
            ("rsi_recovery", "rsi", self.rsi_recovery_level),
        ):
            data[output] = (
                (data[column] > threshold)
                & (data[column].shift(1) <= threshold)
            ).astype(float)
        distance = data["Close"] - data["bollinger_lower"]
        data["band_reentry"] = (
            (distance > 0) & (distance.shift(1) <= 0)
        ).astype(float)
        return data


def generate_backtests(resource_directory: Path = RESOURCE_PATH) -> BacktestIndex:
    """Compare the baseline with responsive and balanced advanced profiles.

    Pass another directory to isolate generated files. The returned index
    references those files, so keep the directory until analysis is finished.
    By default CCXT prepares real market history, including indicator warmup.
    Pass a local data provider to use your own candles instead. Errors
    propagate instead of silently omitting a failed strategy.
    """
    resource_directory = resource_directory.resolve()
    resource_directory.mkdir(parents=True, exist_ok=True)
    app = create_app(config={RESOURCE_DIRECTORY: str(resource_directory)})
    app.add_market(
        market="BITVAVO", trading_symbol="EUR", initial_balance=10_000,
    )
    strategies = [
        RSIEMAStrategy(
            ema_period=10,
            rsi_period=21,
            take_profit_percentage=12,
            stop_loss_percentage=6,
        ),
        TrendPullbackStrategy(
            fast_ema_period=5, slow_ema_period=15, rsi_period=7,
            take_profit_percentage=2.5,
            stop_loss_percentage=1.5,
            rsi_recovery_level=45,
            cooldown_bars=2,
        ),
        TrendPullbackStrategy(
            fast_ema_period=10,
            slow_ema_period=30,
            rsi_period=14,
            take_profit_percentage=4,
            stop_loss_percentage=2.5,
            rsi_recovery_level=50,
            cooldown_bars=3,
        ),
    ]
    study = Study(
        name="Sample Backtest",
        universe=Universe(
            symbols=["BTC"], market="BITVAVO", trading_symbol="EUR",
        ),
        execution_config=ExecutionConfig(trading_costs=[
            TradingCost(symbol="BTC", fee_percentage=0.25),
        ]),
        backtest_windows=[
            BacktestWindow(
                train_range=DATE_RANGE,
                name=(
                    f"window_{DATE_RANGE.start_date}_{DATE_RANGE.end_date}"
                ),
            ),
        ],
        engines=[BacktestEngine.EVENT_DRIVEN],
    )

    return app.run_backtest(
        strategies=strategies,
        study=study,
        run_configuration=BacktestRunConfiguration(
            n_workers=0,
            show_progress=True,
            use_checkpoints=False,
            continue_on_error=False,
            fill_missing_data=True,
        ),
    )


def load_sp500_prices(daterange: BacktestDateRange) -> pd.Series:
    """Use download_v2 for daily ^GSPC closes and a reference before range.

    Daily session dates are marked at 16:00 America/New_York, then converted
    to UTC. This respects daylight saving time and does not expose a close
    before the regular session ends. On early-close days this conservatively
    delays the quote until 16:00. The chart carries completed quotes through
    holidays/weekends; it does not backfill prices from the future.
    """
    result = download_v2(
        symbol="^GSPC", market="YAHOO", time_frame="1d",
        start_date=(
            pd.Timestamp(daterange.start_date).normalize().to_pydatetime()
            - timedelta(days=7)
        ),
        end_date=pd.Timestamp(daterange.end_date).normalize().to_pydatetime(),
        warmup_window=0, pandas=True, save=False,
    )
    history = result.data

    if not isinstance(history, pd.DataFrame):
        raise TypeError("S&P 500 benchmark download must return a DataFrame.")

    if history.empty:
        raise ValueError("Yahoo returned no S&P 500 benchmark history.")

    if not isinstance(history.index, pd.DatetimeIndex):
        raise ValueError("S&P 500 history must have a DatetimeIndex.")

    closes = (
        history.index.tz_localize(None).normalize() + pd.Timedelta(hours=16)
    ).tz_localize("America/New_York").tz_convert("UTC")

    return pd.Series(
        history["Close"].to_numpy(), index=closes, name="S&P 500 (^GSPC)",
    )


def main(
    normalize: bool = True, sp500: bool = False,
) -> None:
    """Overlay normalized curves, or original balances with normalize=False."""
    benchmark = load_sp500_prices(DATE_RANGE) if sp500 else None
    backtests_index = generate_backtests()
    chart = create_layered_equity_chart(
        backtests_index,
        DATE_RANGE,
        normalize=normalize,
        benchmark=benchmark,
        benchmark_label="S&P 500 (^GSPC)",
    )
    chart_path = backtests_index.directory / "layered_equity_chart.html"
    chart_path.write_text(
        '<!doctype html><html><head><meta charset="utf-8">'
        '<title>Layered Equity Chart</title></head><body style="margin:0">'
        + render_chart_html(chart, height=600)
        + '</body></html>',
        encoding="utf-8",
    )

    if not webbrowser.open(chart_path.as_uri()):
        raise RuntimeError(
            f"Could not open a browser. Open {chart_path} manually."
        )


# %% Display: inline in the Interactive Window; browser from the terminal.
if __name__ == "__main__":
    main(normalize=True, sp500=True)
