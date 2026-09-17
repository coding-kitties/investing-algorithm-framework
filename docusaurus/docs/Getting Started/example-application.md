---
sidebar_position: 2
---

# Example Application

This application follows the same workflow as the project README: define one
strategy, screen it with the vector engine, validate it with the event-driven
engine, inspect the persisted results, and run the unchanged strategy in paper
trading.

The example uses an RSI reversal as its primary condition and a recent EMA cross
as confirmation. Declarative rules handle portfolio exposure, position sizing,
scaling, exits, and cooldowns around those decisions.

## Install

```bash
pip install investing-algorithm-framework==9.0.0a17 pyindicators
```

Save the application as `app.py` and run it in one of three modes:

```bash
python app.py --mode vector
python app.py --mode event
python app.py --mode paper
```

Vector and event runs persist `.obtf` bundles under `./my-backtests` and write a
self-contained `backtest-report.html`. Paper mode uses the live event loop with a
simulated portfolio and does not place real orders.

## Complete Application

```python
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
```

## How It Fits Together

### One strategy definition

`RSIEMACrossoverStrategy` does not implement separate vector and event signal
methods. It prepares indicator columns once in `prepare_signal_data`, while its
four `signal_cards` define long entry, long exit, short entry, and short exit.
The framework evaluates those cards in vector backtests, event-driven backtests,
paper trading, and live trading.

Each confluence card requires both parts of the decision:

- The primary RSI condition contributes three points.
- A recent EMA crossover or crossunder contributes two points.
- The five-point threshold means neither condition can create a signal alone.

Decision traces are generated from the same scored rules, so reports can explain
why a signal was accepted or rejected without custom trace-building code.

### Declarative risk controls

Risk behavior lives beside the strategy definition:

- `ExposureRule` reserves at least 20% of the portfolio as unallocated cash.
- `PositionSize` allocates 20% of portfolio value to an entry.
- `ScalingRule` permits controlled additional entries.
- `StopLossRule` protects the full position with a trailing threshold.
- `TakeProfitRule` realizes half the position at its threshold.
- `CooldownRule` limits immediate re-entry and repeated signals.

These rules describe trading intent consistently across execution modes. Some
execution details still differ by engine; use event-driven validation for
trailing exits, order timing, fills, and portfolio interactions.

### Study and `.obtf` results

The `Study` owns the experiment's universe, capital, risk-free rate, engine, and
windows. `app.run_backtest()` returns a disk-backed `BacktestIndex`; complete
orders, trades, signals, snapshots, and study results remain in versioned
`.obtf` bundles until explicitly loaded.

Use `results.df` for scalar filtering and ranking. Load only selected bundles
with `iter_backtests()` or `load_backtests()` when creating a report or inspecting
full run details.

To model rolling, anchored, holdout, walk-forward, time-OOS, or universe-OOS
experiments, add named `BacktestWindow` objects or create another study with a
held-out universe. See [Studies](studies) for those patterns.

### Paper and live trading

Paper mode registers the same strategy and starts the live event loop with a
simulated portfolio. It is useful for validating current data feeds, schedules,
and operational behavior after historical event validation.

Local paper trading does not require exchange credentials. For broker-backed
paper or live trading, provide market-scoped environment variables rather than
hardcoding secrets:

```bash
BITVAVO_API_KEY=<your-api-key>
BITVAVO_SECRET_KEY=<your-api-secret>
```

See [Portfolio Configuration](portfolio-configuration),
[Credential Management](credentials), and [Deployment](deployment) before using
real capital.

## Research Workflow

1. Run `--mode vector` to screen signal behavior and strategy variants quickly.
2. Inspect the `BacktestIndex` and report, then retain credible candidates.
3. Run `--mode event` with the same study definition to validate execution.
4. Run `--mode paper` to verify current data, schedules, and operations.
5. Configure credentials and deployment only after those checks pass.

## Related Guides

- [Strategies](strategies)
- [Studies](studies)
- [Backtesting](backtesting)
- [Vector Backtesting](vector-backtesting)
- [Event-Driven Backtesting](event-backtesting)
- [Backtest Reports](backtest-reports)
- [Confluence Cards](/docs/Advanced%20Concepts/confluence-cards)
- [Risk Rules](/docs/Risk%20Rules/overview)
