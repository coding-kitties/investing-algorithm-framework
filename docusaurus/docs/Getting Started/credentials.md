---
sidebar_position: 3.5
---

# Credential Management

Api keys and secrets are read automatically from environment variables, so
you don't need to hardcode them in `app.py`. If you prefer to pass
credentials explicitly (e.g. from a secrets manager), you can also register
them directly on the app.

## Environment Variables (Recommended)

For every market you register, the framework looks for two environment
variables named after the (uppercased) market identifier:

```bash
BITVAVO_API_KEY=<your_api_key>
BITVAVO_SECRET_KEY=<your_api_secret>
```

With a `.env` file loaded (e.g. via `python-dotenv`), you don't need to pass
any credentials at all:

```python
from dotenv import load_dotenv
from investing_algorithm_framework import create_app

load_dotenv()

app = create_app()
app.add_market(market="bitvavo", trading_symbol="EUR", initial_balance=1000)
```

`app.add_market(...)` registers both the portfolio configuration and a
`MarketCredential` for the market. The standard variables above are
fallbacks: an explicitly passed `api_key` or `secret_key` takes precedence.

For operator-controlled deployments that must replace values supplied by an
entry script, use the explicit override variables:

```bash
BITVAVO_OVERRIDE_API_KEY=<authoritative_api_key>
BITVAVO_OVERRIDE_SECRET_KEY=<authoritative_api_secret>
```

When set, these values override the corresponding `add_market()` arguments.

The override is keyed by the market selected by the `market` argument; it
does not change the configured market or trading symbol.

## Explicit Credentials

If you'd rather source credentials from somewhere else (a secrets manager,
a config file, etc.), register a `MarketCredential` yourself with
`app.add_market_credential(...)`:

```python
from investing_algorithm_framework import MarketCredential

app.add_market_credential(
    MarketCredential(
        market="bitvavo",
        api_key="your_api_key",
        secret_key="your_secret_key",
    )
)
```

Credentials are looked up by market identifier, so this is independent of
`add_market`/`PortfolioConfiguration` — register the portfolio and the
credential separately if you need to pass the credential explicitly:

```python
from investing_algorithm_framework import (
    MarketCredential, PortfolioConfiguration,
)

app.add_portfolio_configuration(
    PortfolioConfiguration(market="bitvavo", trading_symbol="EUR")
)
app.add_market_credential(
    MarketCredential(
        market="bitvavo",
        api_key="your_api_key",
        secret_key="your_secret_key",
    )
)
```

## Credentials for Custom Data Providers

Most OHLCV/ticker data providers (including the built-in CCXT provider)
query public exchange endpoints and don't need credentials at all. If a
custom `DataProvider` needs authenticated access, attach one or more
`MarketCredential` instances to it via the `market_credentials` property:

```python
from investing_algorithm_framework import MarketCredential

data_provider = MyDataProvider(market="bitvavo", data_type="OHLCV")
data_provider.market_credentials = [
    MarketCredential(
        market="bitvavo",
        api_key="your_api_key",
        secret_key="your_secret_key",
    )
]
app.add_data_provider(data_provider)
```

## Next Steps

Now that your credentials are configured, learn how to set up your
[Portfolio Configuration](portfolio-configuration) or create
[Trading Strategies](strategies).
