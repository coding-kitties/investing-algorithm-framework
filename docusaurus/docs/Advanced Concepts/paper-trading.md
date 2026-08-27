---
sidebar_position: 6
---

# Paper Trading

Paper trading lets a strategy run against real (or near-real) market data and place orders exactly as it would live, without ever risking real capital. Enable it per market via `add_market(paper_trading=True, ...)`.

```python
from investing_algorithm_framework import create_app, PaperTradingMode

app = create_app()
app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=1000,  # required — see "Why initial_balance is required" below
    paper_trading=True,
    paper_trading_mode=PaperTradingMode.LOCAL,  # default: PaperTradingMode.AUTO
)
```

## Step 1: Check whether your broker/exchange supports paper trading

Not every exchange runs a sandbox/testnet — CCXT is the source of truth here. Check without needing any credentials:

```python
from investing_algorithm_framework.infrastructure import CCXTOrderExecutor

CCXTOrderExecutor.supports_sandbox_mode("BITVAVO")  # -> True / False
```

This returns `True` only when the exchange advertises a `test` endpoint in CCXT (`exchange.urls["test"]`). Most major exchanges (Binance, Bybit, OKX, ...) do; many smaller/regional ones (including Bitvavo, at the time of writing) don't.

You don't have to check this yourself — passing `paper_trading_mode=PaperTradingMode.AUTO` (the default) makes the framework check for you and pick the best available option automatically. Use the check above only when you want to know in advance, or when deciding between `BROKER` and `LOCAL` explicitly.

## Step 2: What to do based on the result

**If your broker/exchange supports it:**

1. Sign up for/enable the broker's sandbox or testnet account (separate from your live account — check your broker's docs for how to obtain sandbox API credentials).
2. Register those **sandbox-issued** credentials exactly like live credentials — see [Credential Management](../Getting%20Started/credentials). The `<MARKET>_API_KEY` / `<MARKET>_SECRET_KEY` environment variable convention still applies; just put your sandbox keys there instead of live ones.
3. Set `paper_trading_mode=PaperTradingMode.BROKER` (fails loudly if the sandbox turns out to be unavailable — recommended once you know it's supported) or leave it as `AUTO`:

   ```python
   app.add_market(
       market="BINANCE",
       trading_symbol="EUR",
       initial_balance=1000,
       paper_trading=True,
       paper_trading_mode=PaperTradingMode.BROKER,
   )
   ```
4. Run your strategy as normal. Every order now goes to the broker's own sandbox matching engine instead of its live one — nothing else about your strategy code changes.

**If your broker/exchange does not support it:**

1. No sandbox credentials to obtain — the local simulator never makes a network call to place, cancel, or query orders (resolving a fee estimate does make a one-time, unauthenticated `load_markets()` call per exchange — see below).
2. Set `paper_trading_mode=PaperTradingMode.LOCAL` explicitly (or leave `AUTO`, which falls back here automatically):

   ```python
   app.add_market(
       market="BITVAVO",
       trading_symbol="EUR",
       initial_balance=1000,
       paper_trading=True,
       paper_trading_mode=PaperTradingMode.LOCAL,
   )
   ```
3. You can omit `api_key`/`secret_key` entirely — the framework fills in harmless placeholders so credential validation doesn't block startup.
4. Be aware of the [limitations](#limitations) of the local simulator before trusting its results too heavily.

## Two ways execution gets simulated

`paper_trading_mode` picks between two fundamentally different simulation strategies:

### 1. Broker-native sandbox (`PaperTradingMode.BROKER`, or `AUTO` when supported)

Some exchanges run an entirely separate sandbox/testnet environment with its own order book, balances, and matching engine — CCXT exposes this via `exchange.set_sandbox_mode(True)`. When the market's exchange advertises a sandbox endpoint (`exchange.urls["test"]`), the framework routes every order and balance/position query to that sandbox instead of the live endpoint. This is the most realistic simulation available: orders are actually validated and (partially) filled by the real exchange's own matching engine, just against fake money.

This still requires **sandbox-issued credentials** — register them exactly like live credentials (see [Credential Management](../Getting%20Started/credentials)), using the API key/secret your broker issued specifically for its sandbox/testnet.

### 2. Local simulator (`PaperTradingMode.LOCAL`, or `AUTO` fallback)

When the exchange has no sandbox (or you explicitly choose `LOCAL`), the framework simulates execution itself, validated against real OHLCV data — the same way the event-backtest engine validates fills:

- Orders are **not** instant-filled. `PaperTradingOrderExecutor` leaves every order `OPEN`; the event loop's `DefaultTradeOrderEvaluator` only confirms a fill once an OHLCV bar for the order's symbol actually trades through its price — a LIMIT/STOP order fills when the market touches its price, and a MARKET order fills at the open of the next available candle. No network calls are made to place, cancel, or query orders.
- **Cost is estimated realistically by default.** If the strategy or market hasn't configured an explicit `TradingCost`, the executor resolves the exchange's real, publicly advertised taker fee via ccxt's `load_markets()` (cached per exchange) instead of assuming zero cost. Configure a `TradingCost` (with a `fee_percentage`/`slippage_percentage`/`slippage_model`) on the strategy or market to override this with your own assumptions, exactly like in a backtest.
- No real credentials are required — the executor and portfolio provider never touch the network for order operations. If you don't supply `api_key`/`secret_key`, the framework registers harmless placeholder values internally so market-credential validation doesn't block startup.
- The portfolio's cash balance is entirely local: `initial_balance` is the account's *only* funding source. There is no real exchange balance to reconcile against.

## `PaperTradingMode.AUTO` vs. `BROKER` vs. `LOCAL`

| Mode | Behavior when sandbox is available | Behavior when sandbox is unavailable |
|---|---|---|
| `AUTO` (default) | Uses the broker's sandbox | Falls back to the local simulator |
| `BROKER` | Uses the broker's sandbox | Raises `OperationalException` at registration — never silently falls back |
| `LOCAL` | Always uses the local simulator (ignores sandbox support entirely) | Always uses the local simulator |

Use `BROKER` when you specifically need the broker's own order validation/matching behavior and want a loud failure if that guarantee can't be met, rather than silently downgrading to a less realistic simulation.

## Why `initial_balance` is required

A paper-traded portfolio has no real exchange balance to bootstrap from — `PortfolioConfiguration` raises `ImproperlyConfigured` if `paper_trading=True` without an `initial_balance` (or the `INITIAL_BALANCE` environment variable — see below). For broker-sandbox paper trading, the sandbox account still has its own (fake) exchange-side balance, but the framework's own bookkeeping still needs a starting `initial_balance` like any other portfolio.

## Scoping: paper trading never affects other markets

Enabling paper trading for one market registers an `OrderExecutor`/`PortfolioProvider` pair scoped **only** to that market (`priority=0`, so it's picked over the default live CCXT adapters registered for every other market at `priority=3`). A single app can freely mix a paper-traded market and a live-traded market:

```python
app.add_market(market="KRAKEN", trading_symbol="EUR", paper_trading=True, initial_balance=1000)
app.add_market(market="BINANCE", trading_symbol="EUR")  # live, unaffected
```

## Configuring market/trading_symbol/initial_balance from the environment

All three of `market`, `trading_symbol`, and `initial_balance` can be set via environment variables instead of arguments — see [Portfolio Configuration](../Getting%20Started/portfolio-configuration#general-fallbacks-market-trading_symbol-initial_balance). This is particularly useful for paper trading: the same deployed code can be pointed at a different paper-traded market per environment purely through configuration.

## Limitations

- The local simulator has no order-book depth or rejection by the exchange for size/precision. Fills are validated against OHLCV bars (same mechanism as the event-backtest engine), so LIMIT/STOP orders can remain open for multiple iterations until the market actually trades through their price, and MARKET orders fill at the next candle's open rather than instantly.
- The default cost estimate (when no `TradingCost` is configured) is the exchange's advertised **taker** fee only — it doesn't know whether your strategy would actually get maker pricing, and it applies no slippage unless you configure a `TradingCost`/`slippage_model` yourself. If the `load_markets()` lookup fails for any reason (unsupported exchange, no network access), the cost silently falls back to zero rather than raising.
- `PositionMode.HEDGE` is independently backtest-only for the bundled CCXT adapters (see [Position Modes](position-modes)) — this is unrelated to, and not relaxed by, paper trading.
