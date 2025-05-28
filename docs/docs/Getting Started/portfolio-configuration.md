---
---
# Portfolio configuration
In this section we will explain how to configure your portfolio from your broker or exchange.
The framework has by default support for [CCXT](https://github.com/ccxt/ccxt).
CCXT is a library that provides a unified API to interact with multiple brokers and exchanges.

Please have a look at the ccxt documentation to see which brokers and exchanges are supported.

## Configuration of a portfolio
To configure a portfolio you need to create a `PortfolioConfiguration` object.
The `PortfolioConfiguration` object is used to connect your trading bot to your broker or exchange.

The following code snippet shows how to create a `PortfolioConfiguration` object. You must register 
the `PortfolioConfiguration` object with the app in the `app.py` file.

```python
from investing_algorithm_framework import PortfolioConfiguration, create_app

app = create_app()
app.add_portfolio_configuration(
     PortfolioConfiguration(market="BITVAVO", trading_symbol="EUR")
)
```

### Market credentials
To let your portfolio configuration connect the portfolio to the market, you need to specify a market credential of your broker or exchange.
The market credentials holds the API key and secret of your broker or exchange.

The following code snippet shows how to specify the market credentials:

```python
from investing_algorithm_framework import PortfolioConfiguration, create_app, MarketCredentials

app = create_app()
app.add_portfolio_configuration(
     PortfolioConfiguration(
         market="BITVAVO",
         trading_symbol="EUR",
     )
)
app.add_market_credentials(
    MarketCredentials(
        market="BITVAVO",
        api_key=<api_key>,
        api_secret=<api_secret>
    )
)
```

You can also specify the api key and secret in a .env file. The framework will automatically load the credentials from the .env file.
The following code snippet shows how to specify the market credentials in a .env file for the BITVAVO exchange:

> Make sure to specify the API_KEY and SECRET_KEY with the market indentifier prefix. So for example for the BITVAVO exchange
> the API key and secret key should be specified as <MARKET_IDENTIFIER>_API_KEY and <MARKET_IDENTIFIER>_SECRET_KEY which 
> results in the following environment variables: BITVAVO_API_KEY and BITVAVO_SECRET_KEY.

```shell
BITVAVO_API_KEY=<api_key>
BITVAVO_SECRET_KEY=<api_secret>
```

You can then use the following code snippet to load the credentials from the .env file:

```python
from investing_algorithm_framework import PortfolioConfiguration, create_app, MarketCredentials

app = create_app()
app.add_portfolio_configuration(PortfolioConfiguration(market="BITVAVO", trading_symbol="EUR"))
app.add_market_credentials(MarketCredentials(market="BITVAVO"))
```

### Simplified portfolio configuration registration

If you want to register your portfolio configuration and market credentials in a single step, you can use the following
notation for creating a `PortfolioConfiguration` object.

```python
from dotenv import load_dotenv
import os

from investing_algorithm_framework import PortfolioConfiguration, create_app

load_dotenv()

app = create_app()
app.add_portfolio_configuration(
     PortfolioConfiguration(
         market="BITVAVO",
         trading_symbol="EUR",
         api_key=os.getenv("BITVAVO_API_KEY"),
         api_secret=os.getenv("BITVAVO_SECRET_KEY")
     )
)
```

Or if you want to use environment variables, you can use the following code snippet:

```python
from dotenv import load_dotenv
from investing_algorithm_framework import PortfolioConfiguration, create_app

load_dotenv()
app = create_app()
app.add_portfolio_configuration(
     PortfolioConfiguration(
         market="BITVAVO", trading_symbol="EUR",
     )
)
```

In both cases, the framework will automatically create the `MarketCredentials` object for you.

### Specify the maximum size of the portfolio (Initial balance)
If you want to specify the maximum size of your portfolio, you can use the `initial_balance` parameter of your portfolio configuration.
The following code snippet shows how to use the `initial_balance` parameter:

```python
from datetime import datetime
from investing_algorithm_framework import PortfolioConfiguration, create_app

app = create_app()
app.add_portfolio_configuration(
     PortfolioConfiguration(
         market="BITVAVO",
         trading_symbol="EUR",
         initial_balance=1000 # Max unallocated amount of EUR, the rest of your balance of eur at the exchange will be untouched 
     )
)
```