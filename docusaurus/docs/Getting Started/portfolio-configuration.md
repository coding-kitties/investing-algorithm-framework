---
id: portfolio-configuration
title: Configure your portfolio and market credentials
sidebar_label: Portfolio Configuration
---
# Portfolio configuration
In this section we will explain how to configure your portfolio from your broker or exchange.


> The framework has by default support for [CCXT](https://github.com/ccxt/ccxt).
> CCXT is a library that provides a unified API to interact with multiple brokers and exchanges.
> Please have a look at the ccxt documentation to see which brokers and exchanges are supported.

## ✅ Simplified Registration (Recommended)
You can use the following syntax to register a portfolio and credentials (from environment variables) in one step:

```python
app.add_market(
    market="BITVAVO",
    trading_symbol="EUR",
    initial_balance=100  # Optional
)
```

This is the recommended way to register a portfolio. It automatically reads credentials from the .env file using the expected naming convention.

## Basic Configuration with `PortfolioConfiguration`

To configure a portfolio, you need to register a `PortfolioConfiguration` object with the app:

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
To connect to your broker or exchange, you'll need to provide API credentials. 
This is done by registering a MarketCredentials object:

```python
from investing_algorithm_framework import MarketCredentials

app.add_market_credentials(
    MarketCredentials(
        market="BITVAVO",
        api_key="<your_api_key>",
        api_secret="<your_api_secret>"
    )
)
```


## Environment Variable Support
You can also load credentials from a .env file. The framework will
automatically detect them using this naming convention:

```shell
<MARKET_IDENTIFIER>_API_KEY
<MARKET_IDENTIFIER>_SECRET_KEY
```

For example, for the BITVAVO exchange, you would set:

```shell
BITVAVO_API_KEY=<your_api_key>
BITVAVO_SECRET_KEY=<your_api_secret>
```

Then, you can register the portfolio configuration without explicitly passing the credentials:

```python
from investing_algorithm_framework import PortfolioConfiguration, MarketCredentials, create_app
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
    MarketCredentials(market="BITVAVO")
)
```

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

This prevents the bot from using your entire exchange balance.
