# Dedicated dashboard demo

Run a real `ConfluenceScoringStrategy` through vector and event backtesting,
save the results, reopen them, and generate three interactive HTML dashboards.
The demo uses deterministic synthetic BTC/EUR candles, not exchange downloads
or test fixtures. No credentials or network access are needed for backtesting.

## Run

From the repository root, with the framework and `pyindicators` installed:

```bash
python -m examples.dashboard_demo.demo
```

For the repository virtual environment, use `.venv/bin/python` instead of
`python`. The example targets framework v9 and later.

By default, generated files go into the ignored `output/` directory beside
this example:

- `vector.html`: vector-engine results.
- `event.html`: event-engine results.
- `comparison.html`: vector and event results side by side.
- `prices.csv`: 1,200 deterministic two-hour OHLCV candles.
- `vector/backtests/` and `event/backtests/`: persisted `.obtf` bundles and
  indexes. Event runs also capture decision-report sidecars.

The comparison dashboard opens automatically in your default browser, including
when using `--reports-only`. Add `--no-browser` for headless runs or to save
files without opening a tab. You can also open `output/comparison.html` manually.
On WSL, the demo converts the report path with `wslpath` and uses
`powershell.exe` to open your Windows default browser, rather than relying on
a Linux HTML file association. Windows interoperability must be enabled.
The reports are self-contained;
the optional Finterion marketplace connection is the only feature that needs
internet access.

## What to explore

The strategy declares RSI from `pyindicators`, long/short entry and exit cards,
20% position sizing, a 5% stop loss, a 10% take profit, and a two-bar cooldown.
Both engines run the same January-April 2024 historical window.

- Use **Windows** to inspect the periods and select a window on **Overview**.
- Select both engine entries in the sidebar to explore **Compare**.
- Open a strategy page to inspect equity, drawdown, rolling Sharpe, monthly
  returns, and yearly totals.
- Open **Trading** and select BTC in the timeline to inspect intraday trades,
  orders, and any recorded signal rejections.
- Switch themes or capture a chart/table into
  the report builder.

Synthetic prices intentionally create frequent signals. This is a reporting
demo, not a profitable strategy or an assertion that both engines must produce
identical results. The dashboard currently uses its existing renderers;
switching it to the newly extended Finterion Charts library is a separate step.

## Regenerate after dashboard changes

Reuse saved results without running either engine again:

```bash
python -m examples.dashboard_demo.demo --reports-only
```

Choose a different output directory:

```bash
python -m examples.dashboard_demo.demo --output /tmp/iaf-dashboard-demo
python -m examples.dashboard_demo.demo --output /tmp/iaf-dashboard-demo --reports-only
```

Use a separate directory for this demo, not an existing collection of backtests.
The demo refuses to append to an existing results directory, so repeated runs
cannot accidentally add duplicate engine entries. Use `--reports-only` for
dashboard changes or a fresh `--output` directory for another backtest run.
New runs use the same synthetic data and disable checkpoint reuse.
