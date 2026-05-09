# Pipeline API examples

This folder showcases the **Pipeline API (Phase 1)** — a declarative way to
express cross-sectional screens and signals over a panel of symbols, similar
in spirit to Quantopian / Zipline pipelines.

A `Pipeline` is a small class where you declare the columns you want as
`Factor` / `Filter` attributes. The engine turns those declarations into a
single Polars DataFrame on each scheduled run, with no look-ahead, ready for
your `TradingStrategy` to consume via `data["YourPipelineClassName"]`.

## Examples in this folder

| File | What it shows |
| --- | --- |
| [`momentum_screener.py`](momentum_screener.py) | Minimal screener-only example: a `MomentumScreener` ranks 5 EUR pairs by 30‑day return within the top‑3 most liquid names and prints the top‑2 each day. No order placement — useful for understanding the pipeline output format. |
| [`cross_sectional_momentum_bot.py`](cross_sectional_momentum_bot.py) | End-to-end trading bot: a `MomentumScreener` ranks symbols by 30‑day return within the top‑3 most liquid names, and a `TradingStrategy` rebalances daily into the top‑2 ranked symbols on Bitvavo. Includes a 1‑year backtest. |

## Anatomy of the example

```python
class MomentumScreener(Pipeline):
    dollar_volume = AverageDollarVolume(window=30)
    momentum     = Returns(window=30)
    universe     = dollar_volume.top(3)        # liquidity filter
    alpha        = momentum.rank(mask=universe)  # ranked score
```

That's the whole pipeline. The strategy then consumes it:

```python
class CrossSectionalMomentumBot(TradingStrategy):
    pipelines = [MomentumScreener]
    ...

    def run_strategy(self, context, data):
        screen = data["MomentumScreener"]            # polars.DataFrame
        targets = screen.sort("alpha", descending=True).head(TOP_N)
        # ... rebalance into `targets` ...
```

## Run a backtest

From the repository root:

```bash
python examples/cross-sectional-pipelines/cross_sectional_momentum_bot.py
```

The script:

1. Creates an app pointed at `examples/resources/`.
2. Registers OHLCV data sources for 7 EUR pairs on Bitvavo.
3. Runs a 1‑year daily backtest of the momentum rotation.
4. Prints the full `Backtest` JSON (metrics, trades, snapshots).

For an interactive HTML dashboard, replace the `print(backtest)` line with:

```python
from investing_algorithm_framework import BacktestReport
BacktestReport(backtest).show()
```

## Run it live

Remove the `app.run_backtest(...)` block at the bottom of the file and call
`app.run()` instead. Bitvavo does not require API keys for market data, so
the bot will pull live OHLCV out of the box. Add Bitvavo credentials via the
standard config to enable live order execution.

## Built-in factors / filters used

- `AverageDollarVolume(window=N)` — rolling close × volume over N bars.
- `Returns(window=N)` — N‑bar percentage change.
- `Factor.rank(mask=...)` — cross‑sectional rank, optionally restricted to a filter.
- `Factor.top(n)` / `Factor.bottom(n)` — per‑bar top/bottom‑N selection (returns a `Filter`).

See the framework docs:

- `docusaurus/docs/Advanced Concepts/pipelines.md`
- `docusaurus/docs/Advanced Concepts/pipelines-event-backtest.md`
