"""Declarative, three-entry confluence strategy.

Run the offline mask demonstration from the repository root:
    python examples/framework_features/two_hour_confluence_strategy.py

The demonstration does not place orders or contact an exchange.
"""
import pandas as pd

from investing_algorithm_framework import (
    ConfluenceScoringStrategy, ConfluenceScoreConfig, DataSource, ExposureRule,
    IndicatorConfig, IndicatorRule, PositionSize, ScalingRule, Schedule,
    SignalSide, StopLossRule, TimeUnit,
)


def zscore(frame, source_column="Close", period=14, result_column="zscore"):
    rolling = frame[source_column].rolling(period)
    frame[result_column] = (
        frame[source_column] - rolling.mean()
    ) / rolling.std(ddof=0)
    return frame


class TwoHourConfluenceStrategy(ConfluenceScoringStrategy):
    schedule = Schedule.every(2, TimeUnit.HOUR)
    data_sources = [
        DataSource(
            identifier="btc_2h", symbol="BTC/EUR", market="BITVAVO",
            data_type="OHLCV", time_frame="2h", warmup_window=40, pandas=True,
        ),
    ]
    indicator_configs = [
        IndicatorConfig(
            id="z_score_long", data_source="btc_2h", calculate=zscore,
            parameters={
                "source_column": "Close", "period": 14,
                "result_column": "zscore",
            },
            output_columns=["zscore"], minimum_history=14,
            history="continuous", execution="precompute",
        ),
    ]
    confluence_cards = [
        ConfluenceScoreConfig(
            id=name, side=side, scale_in_stage=stage, symbols=["BTC"],
            rules={
                "z_score_oversold": IndicatorRule(
                    indicator_id="z_score_long", output_column="zscore",
                    threshold=threshold, comparison="le",
                    group_weights={"primary": 1}, lookback_period=1,
                ),
            },
            group_aggregation={"primary": "sum"},
            group_thresholds={"primary": 1},
        )
        for name, side, stage, threshold in (
            ("long_entry", SignalSide.OPEN_LONG, None, -2.0),
            ("long_scale_in_one", SignalSide.SCALE_IN, 0, -2.2),
            ("long_scale_in_two", SignalSide.SCALE_IN, 1, -2.4),
        )
    ]
    scaling_rules = [
        ScalingRule(
            symbol="BTC", max_entries=3, initial_entry_percentage=20,
            scale_in_percentage=[40, 40], cooldown_in_bars=2,
        ),
    ]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=40),
    ]
    stop_losses = [
        StopLossRule(
            percentage_threshold=7, sell_percentage=100, symbol="BTC",
            trailing=True, mirror_on_exchange=True,
        ),
    ]
    exposure_rule = ExposureRule(max_portfolio_percentage=80)


def main():
    close = [100 + i / 10 for i in range(40)]
    close += [80, 75, 60, 55, 50, 45, 40, 35]
    data = pd.DataFrame(
        {"Close": close},
        index=pd.date_range(
            "2025-01-01", periods=len(close), freq="2h", tz="UTC",
        ),
    )
    strategy = TwoHourConfluenceStrategy()
    masks = {
        signal.source: signal.series
        for signal in strategy.generate_signal_series({"btc_2h": data})
        if signal.source
    }
    print(pd.DataFrame(masks).tail(8).to_string())
    print(
        "\nRaw masks only: execution enforces cooldowns and fill-driven "
        "stage progression. Use the event engine for this example's "
        "trailing stop and phased portfolio exposure cap."
    )


if __name__ == "__main__":
    main()
