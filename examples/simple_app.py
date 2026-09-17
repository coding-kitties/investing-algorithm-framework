import argparse
from datetime import datetime, timezone

from pyindicators import crossover, crossunder, ema, rsi

from investing_algorithm_framework import (
    BacktestDateRange,
    BacktestEngine,
    BacktestReport,
    BacktestRunConfiguration,
    BacktestWindow,
    ConfluenceCard,
    CooldownRule,
    DataSource,
    DataType,
    EvidenceGroup,
    ExposureRule,
    Operator,
    PositionSize,
    PrimaryGroup,
    ScalingRule,
    Schedule,
    ScoreRule,
    SignalSide,
    StopLossRule,
    Study,
    StudySampleType,
    TakeProfitRule,
    TimeUnit,
    TradingStrategy,
    Universe,
    condition,
    create_app,
)

MARKET = "BITVAVO"
TRADING_SYMBOL = "EUR"
SYMBOL = "BTC"
FULL_SYMBOL = f"{SYMBOL}/{TRADING_SYMBOL}"
INITIAL_CAPITAL = 10_000


def create_confluence_card(name, rsi_operator, rsi_value, cross_column):
    return ConfluenceCard(
        name=name,
        primary=PrimaryGroup(
            name="RSI reversal",
            rules=(
                ScoreRule(
                    name=f"RSI {rsi_operator.value} {rsi_value}",
                    expression=condition(
                        "rsi", rsi_operator, value=rsi_value
                    ),
                    points=3,
                ),
            ),
            minimum_matches=1,
        ),
        secondary=(
            EvidenceGroup(
                name="EMA confirmation",
                rules=(
                    ScoreRule(
                        name="Recent EMA cross",
                        expression=condition(
                            cross_column, Operator.GT, value=0
                        ),
                        points=2,
                    ),
                ),
                minimum_score=2,
            ),
        ),
        minimum_score=5,
    )


class RSIEMACrossoverStrategy(TradingStrategy):
    strategy_id = "rsi_ema_crossover"
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = [SYMBOL]
    data_sources = [
        DataSource(
            identifier="BTC_ohlcv",
            symbol=FULL_SYMBOL,
            data_type=DataType.OHLCV,
            time_frame="2h",
            market=MARKET,
            pandas=True,
            warmup_window=100,
        )
    ]

    exposure_rule = ExposureRule(max_portfolio_percentage=80)
    position_sizes = [
        PositionSize(symbol=SYMBOL, percentage_of_portfolio=20)
    ]
    scaling_rules = [
        ScalingRule(
            symbol=SYMBOL,
            max_entries=3,
            scale_in_percentage=[50, 25],
            cooldown_in_bars=5,
        )
    ]
    stop_losses = [
        StopLossRule(
            symbol=SYMBOL,
            percentage_threshold=5,
            sell_percentage=100,
            trailing=True,
        )
    ]
    take_profits = [
        TakeProfitRule(
            symbol=SYMBOL,
            percentage_threshold=10,
            sell_percentage=50,
        )
    ]
    cooldowns = [
        CooldownRule(
            symbol=SYMBOL,
            trigger="sell",
            blocks="buy",
            bars=12,
        ),
        CooldownRule(trigger="any", blocks="any", bars=2),
    ]

    signal_cards = {
        SignalSide.OPEN_LONG: create_confluence_card(
            "Open long", Operator.LT, 30, "recent_crossover"
        ),
        SignalSide.CLOSE_LONG: create_confluence_card(
            "Close long", Operator.GTE, 70, "recent_crossunder"
        ),
        SignalSide.OPEN_SHORT: create_confluence_card(
            "Open short", Operator.GTE, 70, "recent_crossunder"
        ),
        SignalSide.CLOSE_SHORT: create_confluence_card(
            "Close short", Operator.LT, 30, "recent_crossover"
        ),
    }

    def prepare_signal_data(self, data):
        """Prepare the same decision inputs for every execution mode."""
        frame = data["BTC_ohlcv"].copy()
        frame = ema(frame, "Close", 12, "ema_short")
        frame = ema(frame, "Close", 26, "ema_long")
        frame = crossover(
            frame, "ema_short", "ema_long", "ema_crossover"
        )
        frame = crossunder(
            frame, "ema_short", "ema_long", "ema_crossunder"
        )
        frame = rsi(frame, "Close", 14, "rsi")
        frame["recent_crossover"] = (
            frame["ema_crossover"].rolling(10).max()
        )
        frame["recent_crossunder"] = (
            frame["ema_crossunder"].rolling(10).max()
        )
        return {SYMBOL: frame}


def create_study(engine):
    return Study(
        name="rsi_ema_validation",
        description="RSI reversal with recent EMA confirmation",
        universe=Universe(
            key="btc_eur",
            symbols=[SYMBOL],
            market=MARKET,
            trading_symbol=TRADING_SYMBOL,
        ),
        initial_capital=INITIAL_CAPITAL,
        risk_free_rate=0.027,
        sample_type=StudySampleType.IN_SAMPLE,
        engines=[engine],
        backtest_windows=[
            BacktestWindow(
                name="2023_to_mid_2024",
                train_range=BacktestDateRange(
                    start_date=datetime(
                        2023, 1, 1, tzinfo=timezone.utc
                    ),
                    end_date=datetime(
                        2024, 6, 1, tzinfo=timezone.utc
                    ),
                ),
            )
        ],
    )


def create_configured_app(paper_trading=False):
    app = create_app()
    app.add_market(
        market=MARKET,
        trading_symbol=TRADING_SYMBOL,
        initial_balance=INITIAL_CAPITAL,
        fee_percentage=0.1,
        paper_trading=paper_trading,
    )
    return app


def run_backtest(mode):
    engine = {
        "vector": BacktestEngine.VECTOR,
        "event": BacktestEngine.EVENT_DRIVEN,
    }[mode]

    app = create_configured_app()
    results = app.run_backtest(
        strategy=RSIEMACrossoverStrategy(),
        study=create_study(engine),
        run_configuration=BacktestRunConfiguration(
            backtest_storage_directory="./my-backtests",
            use_checkpoints=True,
            show_progress=True,
        ),
    )

    print(results.df)
    selected_backtests = results.load_backtests(workers=1)
    BacktestReport(backtests=selected_backtests).save(
        "backtest-report.html"
    )
    print(f"Backtest bundles: {results.directory}")
    print("Report: backtest-report.html")


def run_paper_trading():
    app = create_configured_app(paper_trading=True)
    app.add_strategy(RSIEMACrossoverStrategy())
    app.run(run_immediately_on_start=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("vector", "event", "paper"),
        default="vector",
    )
    args = parser.parse_args()

    if args.mode == "paper":
        run_paper_trading()
    else:
        run_backtest(args.mode)


if __name__ == "__main__":
    main()