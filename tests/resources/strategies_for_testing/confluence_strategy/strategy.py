"""Long-only RSI/EMA confluence strategy for BTC/EUR test scenarios."""

import pandas as pd
from pyindicators import ema, rsi

from investing_algorithm_framework import (
    ConfluenceScoreConfig,
    ConfluenceScoringStrategy as BaseConfluenceScoringStrategy,
    DataSource,
    IndicatorConfig,
    IndicatorRule,
    PositionSize,
    Schedule,
    SignalSide,
    TimeUnit,
)


def calculate_ema_spread(data: pd.DataFrame) -> pd.DataFrame:
    ema(data, source_column="Close", period=20, result_column="ema_20")
    ema(data, source_column="Close", period=50, result_column="ema_50")
    data["ema_spread"] = data["ema_20"] - data["ema_50"]
    return data


class ConfluenceScoringStrategy(BaseConfluenceScoringStrategy):
    """Enter on oversold RSI and an uptrend; exit on either reversal.

    Entry requires RSI(14) <= 30 AND EMA(20) > EMA(50).
    Exit requires RSI(14) >= 70 OR EMA(20) < EMA(50).
    Each position uses 25% of the portfolio, with no shorting or scaling.
    """

    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [
        DataSource(
            identifier="BTC_ohlcv",
            symbol="BTC/EUR",
            market="BITVAVO",
            data_type="OHLCV",
            time_frame="2h",
            warmup_window=50,
            pandas=True,
        )
    ]
    indicator_configs = [
        IndicatorConfig(
            id="rsi",
            calculate=rsi,
            timeframe="2h",
            data_source="BTC_ohlcv",
            parameters={
                "source_column": "Close",
                "period": 14,
                "result_column": "rsi",
            },
            output_columns=["rsi"],
            minimum_history=15,
            execution="precompute",
        ),
        IndicatorConfig(
            id="ema_spread",
            calculate=calculate_ema_spread,
            timeframe="2h",
            data_source="BTC_ohlcv",
            output_columns=["ema_spread"],
            minimum_history=50,
            execution="precompute",
        ),
    ]
    confluence_cards = [
        ConfluenceScoreConfig(
            id="long_entry",
            side=SignalSide.OPEN_LONG,
            symbols=["BTC"],
            rules={
                "oversold": IndicatorRule(
                    indicator_id="rsi", output_column="rsi",
                    threshold=30, comparison="le",
                    group_weights={"primary": 1},
                ),
                "uptrend": IndicatorRule(
                    indicator_id="ema_spread", output_column="ema_spread",
                    threshold=0, comparison="gt",
                    group_weights={"primary": 1},
                ),
            },
            group_aggregation={"primary": "sum"},
            group_thresholds={"primary": 2},
        ),
        ConfluenceScoreConfig(
            id="long_exit",
            side=SignalSide.CLOSE_LONG,
            symbols=["BTC"],
            rules={
                "overbought": IndicatorRule(
                    indicator_id="rsi", output_column="rsi",
                    threshold=70, comparison="ge",
                    group_weights={"primary": 1},
                ),
                "downtrend": IndicatorRule(
                    indicator_id="ema_spread", output_column="ema_spread",
                    threshold=0, comparison="lt",
                    group_weights={"primary": 1},
                ),
            },
            group_aggregation={"primary": "sum"},
            group_thresholds={"primary": 1},
        ),
    ]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=25)
    ]
