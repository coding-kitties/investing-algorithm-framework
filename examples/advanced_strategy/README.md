# Advanced multi-signal strategy

A single, self-contained example showing most of the framework's
"building block" mechanisms working together in one strategy, plus a
couple of the framework's other composition points (a `Task`,
`scheduled_functions`).

## What it shows

- **Long *and* short signals from one strategy** (`strategy.py`):
  trend-following longs from an EMA(20)/EMA(50) crossover, and
  mean-reversion shorts from RSI(14) overbought/oversold. See
  `AdvancedMultiSignalStrategy._with_indicators`.
- **Both backtest engines, one strategy**: implements
  `generate_signal_series` (vector engine) *and* `generate_signals`
  (event-driven backtest / live) from the exact same indicator
  columns — swap `run_backtest` for `run_vector_backtest` in
  `backtest.py` and it runs unmodified.
- **Declarative risk management**: a trailing 5% stop loss and a
  fixed 8% take profit, attached via `stop_losses` / `take_profits`.
- **`ConflictPolicy`**: the long and short signals can legitimately
  fire on the same bar (e.g. an EMA crossover during an RSI
  overbought spike); `conflict_policy = ConflictPolicy.default()
  .evolve(on_conflict=ConflictResolution.PRIORITY)` resolves that
  automatically instead of raising.
- **Trade lifecycle hooks**: `on_trade_opened`, `on_trade_closed`,
  `on_trade_stop_loss_triggered`, `on_trade_trailing_stop_loss_triggered`,
  `on_trade_take_profit_triggered` — logging/observability decoupled
  from the signal-generation code.
- **`scheduled_functions`**: `log_daily_exposure` runs once a day,
  independent of the strategy's 2-hour main tick.
- **`Task`** (`tasks.py`): `PortfolioHeartbeatTask` is a periodic job
  that isn't trading logic at all, registered separately via
  `app.add_task(...)`.

## Run

```bash
pip install pyindicators pandas numpy
python backtest.py
```

`generate_data.py` creates a deterministic synthetic OHLCV CSV on
first run (no network, no API keys) with an upward drift plus a
sinusoidal cycle, so both the trend and mean-reversion sides of the
strategy get real opportunities to fire.

## Customising

- Swap the indicators/thresholds in `_with_indicators`.
- Change `conflict_policy` to `ConflictResolution.STRENGTH` to
  arbitrate by signal strength instead of a fixed priority order.
- Add more `stop_losses` / `take_profits` entries for partial
  scale-outs (`sell_percentage < 100`).
- Add more strategies to the same `app` — each strategy in this
  framework runs independently with its own schedule/data sources.
