---
sidebar_position: 3
---

# Recording Custom Variables

During backtesting you often want to track custom indicators, metrics, or signals alongside your trades — for example an RSI value, a moving average, or a custom score. The `record()` API lets you store **any** key-value pair at each backtest iteration so you can analyse it after the run completes.

Recorded values are stored on the `BacktestRun` object and fully support serialization (save & load).

## Event-Driven Backtests

In an event-driven backtest your strategy's `on_run` method receives a `context` object. Call `context.record()` with arbitrary keyword arguments:

```python
from investing_algorithm_framework import TradingStrategy, TimeUnit

class MyStrategy(TradingStrategy):
    time_unit = TimeUnit.DAY
    interval = 1
    symbols = ["BTC"]

    def on_run(self, context, data):
        ohlcv = data["BTC/EUR_1d"]
        close = ohlcv["Close"]

        # Compute any indicator you like
        sma_20 = close.rolling(20).mean().iloc[-1]
        rsi = compute_rsi(close).iloc[-1]

        # Record them — keys can be anything
        context.record(
            sma_20=sma_20,
            rsi=rsi,
            signal_strength=0.85,
        )
```

Each call stores the values together with the current backtest timestamp. You can call `record()` multiple times per iteration — values are appended.

:::tip
`context.record()` is a **no-op** in live mode, so you can leave the calls in your production strategy without any overhead.
:::

## Vectorized Backtests

Vectorized backtests don't use a `context` object. Instead, override `generate_recorded_values()` on your strategy and return a dictionary of `pandas.Series`:

```python
import pandas as pd
from investing_algorithm_framework import TradingStrategy

class MyVectorStrategy(TradingStrategy):
    symbols = ["BTC"]

    def generate_buy_signals(self, data):
        # ... your buy logic ...
        pass

    def generate_sell_signals(self, data):
        # ... your sell logic ...
        pass

    def generate_recorded_values(self, data):
        ohlcv = data["BTC/EUR_1d"]
        close = ohlcv["Close"]

        return {
            "sma_20": close.rolling(20).mean(),
            "rsi": compute_rsi(close),
        }
```

Each key becomes a recorded variable with the Series index as timestamps.

## Accessing Recorded Values

After a backtest completes the recorded values are available on the `BacktestRun`:

```python
from investing_algorithm_framework import create_app

app = create_app()
# ... configure app, add strategy, data sources ...

backtest = app.run_backtest()
run = backtest.backtest_runs[0]

# Dict[str, List[Tuple[datetime, Any]]]
print(run.recorded_values)

# Example: extract RSI time series
for dt, value in run.recorded_values["rsi"]:
    print(f"{dt}: RSI = {value}")
```

### Converting to a DataFrame

You can easily convert recorded values into a pandas DataFrame for plotting or further analysis:

```python
import pandas as pd

rsi_series = pd.Series(
    {dt: val for dt, val in run.recorded_values["rsi"]}
)
sma_series = pd.Series(
    {dt: val for dt, val in run.recorded_values["sma_20"]}
)

df = pd.DataFrame({"rsi": rsi_series, "sma_20": sma_series})
print(df)
```

## Serialization

Recorded values are included when you save and load a `BacktestRun`:

```python
# Save
run.save("/path/to/output")

# Load
from investing_algorithm_framework import BacktestRun
loaded = BacktestRun.open("/path/to/output")
print(loaded.recorded_values)
```

The values are stored in the `run.json` file under the `recorded_values` key.

## Supported Value Types

You can record any JSON-serializable value:

| Type | Example |
|------|---------|
| `float` | `context.record(rsi=70.5)` |
| `int` | `context.record(signal=1)` |
| `str` | `context.record(regime="bullish")` |
| `dict` | `context.record(meta={"score": 0.9})` |
| `list` | `context.record(weights=[0.3, 0.7])` |
| `bool` | `context.record(is_trending=True)` |
