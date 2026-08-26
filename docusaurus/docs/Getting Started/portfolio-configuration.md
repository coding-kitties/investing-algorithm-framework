---
sidebar_position: 3
---

# Portfolio Configuration

In this section we will explain how to configure your portfolio from your broker or exchange.

> The framework has by default support for CCXT. CCXT is a library that
> provides a unified API to interact with multiple brokers and exchanges.
> Please have a look at the ccxt documentation to see which brokers
> and exchanges are supported.

## Simplified Registration (Recommended)

You can use the following syntax to register a portfolio and credentials (from environment variables) in one step:

```python
app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=100  # Optional
)
```

This is the recommended way to register a portfolio. It automatically reads credentials from the .env file using the expected naming convention. See [Credential Management](credentials) for all the ways to configure API keys and secrets.

## Basic Configuration with PortfolioConfiguration

To configure a portfolio, you need to register a PortfolioConfiguration object with the app:

```python
from investing_algorithm_framework import PortfolioConfiguration, create_app

app = create_app()
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="BITVAVO",
        trading_symbol="EUR"
    )
)
```

## Market Credentials

To connect to your broker or exchange, you'll need to provide API credentials. This is done by registering a `MarketCredential` object:

```python
from investing_algorithm_framework import MarketCredential

app.add_market_credential(
    MarketCredential(
        market="BITVAVO",
        api_key="<your_api_key>",
        secret_key="<your_api_secret>"
    )
)
```

## Environment Variable Support

You can also load credentials from a .env file. The framework will automatically detect them using this naming convention:

```
<MARKET_IDENTIFIER>_API_KEY
<MARKET_IDENTIFIER>_SECRET_KEY
```

For example, for the BITVAVO exchange, you would set:

```bash
BITVAVO_API_KEY=<your_api_key>
BITVAVO_SECRET_KEY=<your_api_secret>
```

Then, you can register the portfolio configuration without explicitly passing the credentials:

```python
from investing_algorithm_framework import PortfolioConfiguration, MarketCredential, create_app
from dotenv import load_dotenv

load_dotenv()
app = create_app()

app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="BITVAVO",
        trading_symbol="EUR"
    )
)
app.add_market_credential(
    MarketCredential(market="BITVAVO")
)
```

See [Credential Management](credentials) for the full picture (explicit credentials, custom data providers, etc.).

## Configuring Market, Trading Symbol and Initial Balance from Environment Variables

`market`, `trading_symbol`, and `initial_balance` can also be sourced from environment variables instead of hardcoding them — useful when the same code is deployed to multiple environments (e.g. a Docker image that trades a different market per deployment):

```
MARKET=<market_identifier>
TRADING_SYMBOL=<trading_symbol>
INITIAL_BALANCE=<initial_balance>
```

For example:

```bash
MARKET=BITVAVO
TRADING_SYMBOL=EUR
INITIAL_BALANCE=1000
```

With those set, both of the following are equivalent — arguments you do pass always take precedence over the environment variables:

```python
app.add_market()
```

```python
from investing_algorithm_framework import PortfolioConfiguration

app.add_portfolio_configuration(PortfolioConfiguration())
```

A missing `market` or `trading_symbol` (neither an argument nor an environment variable) raises an `ImproperlyConfigured` error at registration time.

## Initial Balance (Max Portfolio Size)

You can optionally define the maximum unallocated size of your portfolio using the initial_balance parameter:

```python
from investing_algorithm_framework import PortfolioConfiguration, create_app

app = create_app()
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="BITVAVO",
        trading_symbol="EUR",
        initial_balance=1000  # Unallocated EUR to be managed by the bot
    )
)
```

or with the simplified registration (recommended):

```python
app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=1000  # Unallocated EUR to be managed by the bot
)
```

This prevents the algorithm from using your entire exchange balance.

## Position Mode: NETTING vs. HEDGE

By default, a portfolio only ever holds one direction (long or short) per symbol at a time (`PositionMode.NETTING`). Set `position_mode=PositionMode.HEDGE` to let a strategy hold an independent long **and** short position on the same symbol simultaneously:

```python
from investing_algorithm_framework import PortfolioConfiguration, PositionMode

app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    position_mode=PositionMode.HEDGE,  # default: PositionMode.NETTING
)
```

`HEDGE` is currently backtest-only for the bundled CCXT adapters. See [Position Modes](../Advanced%20Concepts/position-modes) for the full picture, including live-trading requirements for custom adapters.

## Paper Trading

Set `paper_trading=True` to run against a market without ever placing a real order — useful for validating a strategy against live/near-live data before risking real capital:

```python
app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=1000,  # required for paper trading — there is no
                           # real exchange balance to seed the account
    paper_trading=True,
)
```

`paper_trading_mode` controls how execution is simulated:

- `PaperTradingMode.AUTO` (default): use the broker's own sandbox/testnet if its exchange advertises one; otherwise fall back to the framework's local simulator.
- `PaperTradingMode.BROKER`: require the broker's sandbox/testnet. Raises an error at registration time if it isn't available — never silently falls back.
- `PaperTradingMode.LOCAL`: always use the framework's local, broker-agnostic simulator. No network calls are ever made to place orders; every order fills immediately at its requested price. No real credentials are required.

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

When the broker's sandbox is used (`BROKER`, or `AUTO` when supported), you still need sandbox-issued API credentials for that market — register them the same way as live credentials (see [Credential Management](credentials)), just using the keys your broker issued for its sandbox/testnet environment.

## Next Steps

Now that you have your portfolio configured, learn how to create [Trading Strategies](strategies) that will use this portfolio configuration.

