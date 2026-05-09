# Strategy Showcase

This folder contains one subfolder per strategy *type*. The goal is to show how
to implement different logic patterns and data requirements with the
`investing_algorithm_framework`, and to provide a starting point for your own
research. **The strategies are intentionally simple and are not meant to be
profitable as-is** — they are reference implementations of a pattern, not
production-grade alpha.

Each subfolder is self-contained and ships with:

- `README.md` — what the strategy is, why it exists, fit level, parameters, caveats.
- `strategy.py` — the `TradingStrategy` (or pipeline) implementation.
- `backtest.py` — a runnable script that wires the strategy into an app and
  runs a backtest over a recent date range.
- `requirements.txt` — Python dependencies for that specific subfolder.

If a strategy type cannot be implemented today with the framework, the
subfolder contains **only a `README.md`** explaining *why* it is currently not
possible and what would be needed to make it possible.

## Fit legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Sweet spot — framework is well-suited and example is end-to-end runnable. |
| 🟢 | Workable — implementable with some bookkeeping in user code. |
| 🟡 | Partial — pattern is shown but a key primitive is approximated. |
| 🔴 | Not currently possible — README only, explains why. |

## Index

### 1. Position-taking strategies (signal → orders)

| # | Strategy | Fit | Description |
|---|----------|-----|-------------|
| 01 | [trend_following](./01_trend_following) | ✅ | Vector backtest of an EMA crossover. |
| 02 | [mean_reversion](./02_mean_reversion) | ✅ | Buy oversold, sell overbought (Bollinger + RSI). |
| 03 | [cross_sectional_momentum](./03_cross_sectional_momentum) | ✅ | Pipeline ranks symbols by 30d return, holds top-N. |
| 04 | [multi_factor_portfolio](./04_multi_factor_portfolio) | ✅ | Pipeline blends momentum + low-vol + liquidity factors. |
| 05 | [pairs_trading](./05_pairs_trading) | 🟢 | Z-score on BTC/ETH log-price spread. |
| 06 | [funding_rate_carry](./06_funding_rate_carry) | 🟡 | Carry pattern shown, but no native perp/funding-rate data provider. |
| 07 | [event_driven_signal](./07_event_driven_signal) | ✅ | Volatility-breakout entry on bar-close events. |
| 08 | [dca_accumulation](./08_dca_accumulation) | ✅ | Scheduled fixed-size buys (dollar-cost averaging). |

### 2. Portfolio construction strategies

| # | Strategy | Fit | Description |
|---|----------|-----|-------------|
| 09 | [risk_parity](./09_risk_parity) | ✅ | Inverse-volatility weighting, monthly rebalance. |
| 10 | [mean_variance_markowitz](./10_mean_variance_markowitz) | ✅ | Quarterly Markowitz optimisation (`scipy`). |
| 11 | [hierarchical_risk_parity](./11_hierarchical_risk_parity) | ✅ | López de Prado HRP with `scipy` clustering. |
| 12 | [vol_targeting_overlay](./12_vol_targeting_overlay) | ✅ | Scales gross exposure to a target portfolio vol. |

### 3. Execution strategies

| # | Strategy | Fit | Description |
|---|----------|-----|-------------|
| 13 | [twap_vwap_execution](./13_twap_vwap_execution) | 🟡 | Bar-level TWAP slicing of a parent order. |
| 14 | [implementation_shortfall](./14_implementation_shortfall) | 🔴 | Needs intra-bar fills the framework does not currently model. |
| 15 | [iceberg_orders](./15_iceberg_orders) | 🔴 | Requires venue-side iceberg primitives not abstracted by the framework. |

### 4. Derivatives strategies

| # | Strategy | Fit | Description |
|---|----------|-----|-------------|
| 16 | [options_selling_income](./16_options_selling_income) | 🔴 | No options instrument / chain primitives in the framework today. |
| 17 | [volatility_trading](./17_volatility_trading) | 🔴 | Requires a vol surface and option pricing pipeline. |
| 18 | [delta_hedged_options](./18_delta_hedged_options) | 🔴 | Requires Greeks pipeline and options venue support. |
| 19 | [futures_basis_calendar](./19_futures_basis_calendar) | 🟡 | Pattern shown on spot proxy; no native futures-curve data model. |

### 5. Slow market making

| # | Strategy | Fit | Description |
|---|----------|-----|-------------|
| 20 | [slow_market_making](./20_slow_market_making) | 🟢 | Posts limit orders around mid every bar; capped inventory. |

### 6. High-frequency / sub-second strategies (not currently possible)

| # | Strategy | Fit | Description |
|---|----------|-----|-------------|
| 21 | [active_market_making](./21_active_market_making) | 🔴 | Requires sub-ms event loop and L2 book — see `iaf_realtime` plan. |
| 22 | [latency_arbitrage](./22_latency_arbitrage) | 🔴 | Requires colocated low-latency venue connectivity. |
| 23 | [hft](./23_hft) | 🔴 | Bar-driven event loop is too slow for true HFT. |
| 24 | [orderbook_microstructure](./24_orderbook_microstructure) | 🔴 | No L2 order-book data model. |
| 25 | [news_nlp_subsecond](./25_news_nlp_subsecond) | � | Event-driven trigger model planned — see [#534](https://github.com/coding-kitties/investing-algorithm-framework/issues/534). |
| 26 | [ml_inference_high_freq](./26_ml_inference_high_freq) | 🔴 | Inference loop dominated by per-iteration overhead. |

## Running an example

```bash
cd examples/strategies_showcase/01_trend_following
pip install -r requirements.txt
python backtest.py
```

Backtests fetch OHLCV from the public BITVAVO endpoint via `ccxt` (no API
keys required for market data). The first run will download data and cache
it; subsequent runs reuse the cache.

