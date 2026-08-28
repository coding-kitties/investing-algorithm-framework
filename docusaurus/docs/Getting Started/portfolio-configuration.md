---
sidebar_position: 3
---

# Portfolio Configuration

Portfolio configuration tells IAF which market to use, which currency funds
the portfolio, and how that portfolio should behave — its credentials, its
starting balance, its trading costs, its position mode, and whether it
trades live or on paper. Market names, trading symbols, and explicit
portfolio identifiers are all normalized to uppercase.

> The framework has by default support for CCXT. CCXT is a library that
> provides a unified API to interact with multiple brokers and exchanges.
> Please have a look at the ccxt documentation to see which brokers
> and exchanges are supported.

## Quick Start

The recommended way to configure a portfolio is a single `add_market()`
call, which registers both the portfolio configuration and its market
credential in one step:

```python
app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=100,  # optional for live trading
)
```

Beyond `market`, `trading_symbol`, and `initial_balance`, the same call also
accepts credentials, market-level fees and slippage, position mode, and
built-in paper trading — each covered in its own section below. Register a
given market only once per app: portfolio configurations are list-based,
while credentials and adapter selection are keyed by market, so a repeat
call for the same market silently replaces earlier registrations rather
than merging with them.

Everything in this guide assumes `add_market()` unless stated otherwise. See
[Direct Registration with PortfolioConfiguration](#direct-registration-with-portfolioconfiguration)
near the end of this page for the lower-level alternative.

## Environment Variables

IAF reads configuration from the **process environment**; it never loads a
`.env` file itself. If your credentials live in a `.env` file, call
`load_dotenv()` yourself before `add_market()`, or let your deployment
platform inject the variables directly. Three tiers of environment
variables are recognized, each with different precedence rules.

### General fallbacks: `market`, `trading_symbol`, `initial_balance`

`market`, `trading_symbol`, and `initial_balance` fall back to
environment variables whenever their argument is omitted:

```bash
MARKET=BITVAVO
TRADING_SYMBOL=EUR
INITIAL_BALANCE=1000
```

```python
app.add_market()
```

```python
from investing_algorithm_framework import PortfolioConfiguration

app.add_portfolio_configuration(PortfolioConfiguration())
```

These are pure fallbacks — an explicit argument always takes precedence, so
`add_market(market="binance", ...)` is never redirected by a `MARKET`
environment variable. A missing `market` or `trading_symbol` (neither an
argument nor an environment variable) raises `ImproperlyConfigured` at
registration; `INITIAL_BALANCE` must parse as a number when set.

### Credential fallbacks: `<MARKET>_API_KEY`, `<MARKET>_SECRET_KEY`

Credentials use an uppercased, market-scoped naming convention:

```bash
BITVAVO_API_KEY=<your_api_key>
BITVAVO_SECRET_KEY=<your_api_secret>
```

Like the general fallbacks above, these are only consulted when the
corresponding argument is `None` — an explicit `api_key`/`secret_key`
passed to `add_market()`, or to a directly constructed `MarketCredential`,
always wins:

```python
from dotenv import load_dotenv
from investing_algorithm_framework import create_app

load_dotenv()
app = create_app()
app.add_market(market="BITVAVO", trading_symbol="EUR")
```

Credential resolution and adapter-specific validation happen during app
initialization, not merely when `add_market()` is called. Local paper
trading is the exception: it needs no real credentials and supplies
harmless internal placeholders when credentials are omitted. See
[Credential Management](credentials) for the full picture, including
explicit credentials and custom data providers.

### Deployment overrides: `<MARKET>_OVERRIDE_*`

For deployments that need to *guarantee* a value takes effect — for
example a hosting platform that must inject sandbox credentials regardless
of what a tenant's own entry script passes — `add_market()` also recognizes
an explicit `OVERRIDE` namespace:

```bash
BITVAVO_OVERRIDE_API_KEY=<sandbox-or-live-api-key>
BITVAVO_OVERRIDE_SECRET_KEY=<sandbox-or-live-secret>
BITVAVO_OVERRIDE_PAPER_TRADING=true
BITVAVO_OVERRIDE_PAPER_TRADING_MODE=local
BITVAVO_OVERRIDE_INITIAL_BALANCE=1000
```

Unlike the fallback variables above, these **replace** the corresponding
`add_market()` argument whenever set, regardless of what was passed:
`<MARKET>_OVERRIDE_API_KEY` and `<MARKET>_OVERRIDE_SECRET_KEY` override
`api_key`/`secret_key`, `<MARKET>_OVERRIDE_PAPER_TRADING`/
`<MARKET>_OVERRIDE_PAPER_TRADING_MODE` override `paper_trading`/
`paper_trading_mode`, and `<MARKET>_OVERRIDE_INITIAL_BALANCE` overrides
`initial_balance` — including a value hardcoded in an entry script. The
prefix comes from the market already selected by the call — these
variables never redirect `market` or `trading_symbol` themselves.

Paper-trading booleans accept `true`/`false`, `yes`/`no`, `on`/`off`, and
`1`/`0`, case-insensitively. Modes accept `auto`, `broker`, and `local`,
also case-insensitively. `INITIAL_BALANCE` must parse as a number.
Invalid values fail fast with `ImproperlyConfigured`.

These overrides apply only to `add_market()`. Directly constructed
`PortfolioConfiguration` objects only read the general fallback variables
(`MARKET`, `TRADING_SYMBOL`, `INITIAL_BALANCE`), and directly constructed
`MarketCredential` objects only read the standard credential fallbacks
(`<MARKET>_API_KEY`, `<MARKET>_SECRET_KEY`).

## Initial Balance

`initial_balance` sets the portfolio's initial managed cash, with slightly
different meaning depending on how the portfolio trades:

- **Live trading:** when set, it caps how much of the exchange's available
  trading-currency balance IAF initially manages. The exchange must have at
  least that amount available. When omitted, IAF adopts the full available
  balance during first synchronization.
- **Local paper trading:** it funds the simulated account and is required —
  there's no real exchange balance to seed it from.
- **Broker-sandbox paper trading:** still required for IAF's own
  bookkeeping, even though the sandbox account also has its own fake
  exchange-side balance.
- **Backtesting:** it provides starting capital unless the backtest or
  study supplies its own initial amount.

```python
app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=1000,
)
```

For a persisted live portfolio, changing the configured initial balance
does not resize the existing portfolio — IAF rejects the mismatch at
startup rather than silently changing its managed balance.

## Default Fees and Slippage

`fee_percentage` and `slippage_percentage` set market-level defaults
applied to every symbol traded on that market. Values are percentage
points, so `0.1` means 0.1%, not 10%:

```python
app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    fee_percentage=0.10,
    slippage_percentage=0.05,
)
```

A symbol-specific `TradingCost` on a strategy takes precedence over these
market-level defaults. Fixed fees and custom slippage models are only
available through `TradingCost`, not `add_market()`. See
[TradingCost](../Risk%20Rules/trading-cost) for the full calculation
details and resolution order.

## Position Mode: NETTING vs. HEDGE

By default, a portfolio holds only one direction per symbol at a time
(`PositionMode.NETTING`). Set `position_mode=PositionMode.HEDGE` to allow
independent long and short legs on the same symbol:

```python
from investing_algorithm_framework import PositionMode

app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    position_mode=PositionMode.HEDGE,  # default: PositionMode.NETTING
)
```

Both backtest engines support `HEDGE` out of the box. In live and paper
runs, the selected order executor and portfolio provider must explicitly
advertise HEDGE support — the bundled CCXT and local paper adapters
currently support only `NETTING`, so built-in live/paper trading is
effectively NETTING-only unless you supply a custom, HEDGE-capable adapter.
This capability check happens during startup. See
[Position Modes](../Advanced%20Concepts/position-modes) for the full
picture.

## Paper Trading

Set `paper_trading=True` to test a strategy against live or near-live
market data without ever placing a real order. An `initial_balance` is
required in every paper mode (see [Initial Balance](#initial-balance)
above):

```python
app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=1000,
    paper_trading=True,
)
```

`paper_trading_mode` controls how execution is simulated:

- `PaperTradingMode.AUTO` (default): use the broker's sandbox/testnet when
  both bundled adapters support it; otherwise fall back to the local
  simulator.
- `PaperTradingMode.BROKER`: require the broker's sandbox. `add_market()`
  raises `OperationalException` at registration if it's unavailable —
  never silently falls back.
- `PaperTradingMode.LOCAL`: always use IAF's broker-agnostic simulator. It
  makes no broker calls to place, cancel, or query orders and requires no
  real credentials. Market-data providers may still use the network.

```python
from investing_algorithm_framework import PaperTradingMode

app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=1000,
    paper_trading=True,
    paper_trading_mode=PaperTradingMode.LOCAL,
)
```

Local orders are not instant-filled. They initially remain `OPEN` and are
evaluated against subsequent OHLCV candles: LIMIT and STOP orders fill when
the market touches their price, while MARKET orders fill at the next
available candle's open. If no explicit trading cost is configured, IAF may
perform one cached, unauthenticated CCXT market-metadata request to
estimate the exchange's taker fee.

Broker-sandbox mode still requires sandbox-issued credentials, usually
different from your production keys — register or inject them using the
same [credential conventions](#credential-fallbacks-market_api_key-market_secret_key)
as live trading. See [Paper Trading](../Advanced%20Concepts/paper-trading)
for full execution and fill details.

## Direct Registration with PortfolioConfiguration

For advanced use, you can register a `PortfolioConfiguration` and
`MarketCredential` separately instead of going through `add_market()`:

```python
from investing_algorithm_framework import (
    MarketCredential,
    PortfolioConfiguration,
    create_app,
)

app = create_app()
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="BITVAVO",
        trading_symbol="EUR",
    )
)
app.add_market_credential(
    MarketCredential(
        market="BITVAVO",
        api_key="<your_api_key>",
        secret_key="<your_api_secret>",
    )
)
```

Direct construction additionally exposes `identifier`, `track_from`, and
`deposit_schedule`, none of which `add_market()` accepts. The identifier
defaults to the market name; `deposit_schedule` is used by vector
backtests.

Direct registration does **not** configure built-in paper executors or
providers — use `add_market()` whenever you need IAF's `AUTO`, `BROKER`, or
`LOCAL` paper-trading modes. Setting `paper_trading=True` directly on a
`PortfolioConfiguration` records and validates the flag, but doesn't wire
the paper-trading infrastructure or placeholder credentials on its own.

## Next Steps

Now that you have your portfolio configured, learn how to create [Trading Strategies](strategies) that will use this portfolio configuration.

