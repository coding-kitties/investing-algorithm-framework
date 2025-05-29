---
slug: how-to-create-a-trading-bot-in-5-steps
authors:
    name: Marc van Duyn
    title: How to create a trading bot
    url: https://github.com/mduyn
    image_url: https://github.com/mduyn.png
tags: [trading bot, deployment, azure functions, aws lambda, crypto, investing algorithm, investing algorithm framework]
---

# How to build a trading bot in 5 steps
Would you like to build your own trading bot but do not know where to start? You have come to the right place.
In this guide we will walk you through the four steps of building a trading bot, and get you started with automated trading!

> All source code for this blog can be found [here](https://github.com/MDUYN/trading-bot-example).
> The code is written in Python 3.9.6 and the main framework used is the [Investing algorithm framework](https://investing-algorithm-framework.com) for building the trading bot.
> If you are interested in using a trading bot, but do not want to build one yourself or if you would like to
> make you trading bot available for other to use, you can check out [Finterion](https://finterion.com).

## 1 Choosing the right framework
There are a many libraries, packages and resources available to build a trading bot. To find the right
tools for you consider looking at the following list of [resources](https://wilsonfreitas.github.io/awesome-quant/).
For this blog we will use the [Investing algorithm framework](https://github.com/coding-kitties/investing-algorithm-framework).
This is a Python based framework that allows you to build your own trading bot. It is open-source and free to use.

## 2 Creating a trading bot with the investing algorithm framework
The investing algorithm framework has various options to build your own trading bot and implement a strategy.
Some key questions to consider when building your strategy are:

* How often should my bot run?
* Which market data should my bot use?
* Which indicators should my bot use?
* On which exchange or broker should my bot trade?
* How do I deploy my bot?

For our trading bot we would like to implement a simple strategy that buys and sells the cryptocurrency
bitcoin based on a set of simple indicators. The strategy will run every 2 hours. This means that every 2 hours the bot will
check the price of bitcoin and decide whether to buy or sell.

### 2.1 Setting up the trading bot
To set up the trading bot, we first need to install the investing algorithm framework.

```bash
pip install investing-algorithm-framework
```

### 2.2 Specifying our market data
Next, we need specify how often our trading bot runs and which market data it's going to use.
The investing algorithm framework supports various types of market data. For this example we will use the
historical price data of bitcoin in candle stick format. In trading terms this is called
OHLCV (Open, High, Low, Close, Volume) data. In order to specify this in the framework we need
to register a trading strategy with the framework. We do this in the following way:

```python
from datetime import datetime, timedelta

from investing_algorithm_framework import CCXTOHLCVMarketDataSource, \
    CCXTTickerMarketDataSource

bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR-ohlcv",
    market="BITVAVO",
    symbol="BTC/EUR",
    timeframe="2h",
    # We want to retrieve data from the last 3 days (3 days * 24 hours * 4(15m) = 288 candlesticks)
    start_date_func=lambda: datetime.utcnow() - timedelta(days=17)
)
# Ticker data to track orders, trades and positions we make with symbol BTC/EUR
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC/EUR-ticker",
    market="BITVAVO",
    symbol="BTC/EUR",
)
```

### 2.3 Specifying our trading strategy
Now that we have set up the market data sources for our trading bot, we can implement the trading strategy. For this example we will
implement a simple strategy that buys bitcoin when there is a golden cross between a fast and slow moving average.
The golden cross is a bullish signal that occurs when the short-term (fast) moving average crosses
above a long-term (slow) moving average.

For the sell signal we will use the opposite. We will sell bitcoin when there is a death cross between the fast and the slow
moving average period. The death cross is a bearish signal that occurs when the short-term (fast) moving average crosses below
the long-term (slow) moving average.

So to summarize:
When the fast moving average crosses above the slow moving average, we buy. When the fast moving average crosses
below the slow moving average, we sell.

In order to implement this strategy we need to use the market data that we have retrieved from the exchange. We will
use the OHLCV (candlestick) data to calculate the moving averages and we will use ticker data to get the most recent price of bitcoin.

> This code uses tulipy to calculate the moving averages. Tulipy is a Python binding for the technical analysis library (tulipindicators)[https://tulipindicators.org/].

Creat a new file called strategy.py and add the following code:

```python
from investing_algorithm_framework import TradingStrategy, TimeUnit, Algorithm

class GoldenCrossDeathCrossTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    market_data_sources = [
        "BTC/EUR-ohlcv",
        "BTC/EUR-ticker",
    ]
    symbols = ["BTC/EUR"]

    def apply_strategy(self, algorithm: Algorithm, market_data: dict):
        pass
```

Then we implement the apply_strategy method. This method is called every time
the trading strategy is executed. As defined above the strategy is run
every 2 hours.

In the `apply_strategy` we first check if we have any open orders for a symbol.
If we do not have any open order we check if there is a golden cross or a death cross.

> The reason we check if there are any open orders first is because we do not want to open a new order
> when we already have an open order that has not yet been closed (filed) by the exchange.
> We only want to open a new position when we do not have any open orders.

```python
from investing_algorithm_framework import TradingStrategy, TimeUnit, Algorithm
import tulipy as tp
import pandas as pd

class GoldenCrossDeathCrossTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    market_data_sources = [
        "BTC/EUR-ohlcv",
        "BTC/EUR-ticker",
    ]
    symbols = ["BTC/EUR"]

    def apply_strategy(self, algorithm: Algorithm, market_data: dict):
        
        for symbol in self.symbols:
            target_symbol = symbol.split('/')[0]
            
            # Don't open a new order when we already have an open order
            if algorithm.has_open_orders(target_symbol):
                continue
    
            ohlcv_data = market_data[f"{symbol}-ohlcv"]
            df = pd.DataFrame(
                ohlcv_data,
                columns=['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']
            )
            # Fast moving average
            fast = tp.sma(df["Close"].to_numpy(), period=9)
            # Slow moving average
            slow = tp.sma(df["Close"].to_numpy(), period=50)
            # Current price of symbol (BTC/EUR)
            price = market_data[f"{symbol}-ticker"]["bid"]
```

Next we check if there is a golden cross or a death cross. If there is a
golden cross we buy bitcoin. If there is a death cross we sell bitcoin.

```python
from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    Algorithm, OrderSide
import tulipy as tp
import pandas as pd

def is_crossover(fast_series, slow_series):
    """
    Expect df to have columns: Date, ma_<period_one>, ma_<period_two>.
    With the given date time it will check if the ma_<period_one> is a
    crossover with the ma_<period_two>
    """

    return fast_series[-2] <= slow_series[-2] \
           and fast_series[-1] > slow_series[-1]


def is_crossunder(fast_series, slow_series):
    """
    Expect df to have columns: Date, ma_<period_one>, ma_<period_two>.
    With the given date time it will check if the ma_<period_one> is a
    crossover with the ma_<period_two>
    """

    return fast_series[-2] >= slow_series[-2] \
        and fast_series[-1] < slow_series[-1]


class GoldenCrossDeathCrossTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    market_data_sources = [
        "BTC/EUR-ohlcv",
        "BTC/EUR-ticker",
    ]
    symbols = ["BTC/EUR"]

    def apply_strategy(self, algorithm: Algorithm, market_data: dict):

        for symbol in self.symbols:
            target_symbol = symbol.split('/')[0]
            
            # Don't open a new order when we already have an open order
            if algorithm.has_open_orders(target_symbol):
                continue

            ohlcv_data = market_data[f"{symbol}-ohlcv"]
            df = pd.DataFrame(
                ohlcv_data,
                columns=['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']
            )
            fast = tp.sma(df["Close"].to_numpy(), period=9)
            slow = tp.sma(df["Close"].to_numpy(), period=50)
            price = market_data[f"{symbol}-ticker"]["bid"]

            if algorithm.has_position(target_symbol) and is_crossunder(fast, slow):
                algorithm.close_position(target_symbol)
            elif not algorithm.has_position(target_symbol) and is_crossover(fast, slow):
                algorithm.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4
                )
```

## 3 Testing our trading strategy
Now that we have implemented our trading strategy we can test it. To test our strategy we will use the
backtesting functionality of the investing algorithm framework. This allows us to test our strategy on historical data.

Create a new file called `backtest.py` and add the following code:

```python
import sys
from datetime import datetime

from investing_algorithm_framework import PortfolioConfiguration, \
    pretty_print_backtest

from app import app


def convert_to_datetime(datetime_str):
    try:
        return datetime.strptime(datetime_str, "%Y-%m-%d")
    except ValueError:
        print(f"Error: Invalid datetime format for '{datetime_str}'. Please use the format 'YYYY-MM-DD HH:MM:SS'")
        sys.exit(1)


app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="BITVAVO",
        trading_symbol="EUR",
        initial_balance=400
    )
)

if __name__ == "__main__":

    if len(sys.argv) != 3:
        print(
            "Error: Please provide two datetime "
            "strings as command-line arguments."
        )
        sys.exit(1)

    # Get datetime strings from command-line arguments
    start_date_str = sys.argv[1]
    end_date_str = sys.argv[2]

    # Convert datetime strings to datetime objects
    start_date = convert_to_datetime(start_date_str)
    end_date = convert_to_datetime(end_date_str)
    backtest_report = app.backtest(
        start_date=start_date,
        end_date=end_date,
        pending_order_check_interval="2h"
    )
    pretty_print_backtest(backtest_report)
```

Running this code will give you the following output:

```bash
$ python backtest 2023-01-01 2023-12-30
====================Backtest report===============================
* Start date: 2023-01-01 00:00:00
* End date: 2023-12-30 00:00:00
* Number of days: 363
* Number of runs: 4357
====================Portfolio overview============================
* Number of orders: 128
* Initial balance: 400.0000 EUR
* Final balance: 468.1028 EUR
* Total net gain: 68.1028 EUR
* Total net gain percentage: 17.0257%
* Growth rate: 17.0257%
* Growth 68.1028 EUR
====================Positions overview========================
╭────────────┬──────────┬──────────────────┬──────────────┬───────────────┬───────────────────────────┬────────────────┬───────────────╮
│ Position   │   Amount │   Pending amount │   Cost (EUR) │   Value (EUR) │ Percentage of portfolio   │   Growth (EUR) │ Growth_rate   │
├────────────┼──────────┼──────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ EUR        │  468.103 │                0 │      468.103 │       468.103 │ 100.0000%                 │              0 │ 0.0000%       │
╰────────────┴──────────┴──────────────────┴──────────────┴───────────────┴───────────────────────────┴────────────────┴───────────────╯
====================Trades overview===========================
* Number of trades closed: 64
* Number of trades open: 0
* Percentage of positive trades: 29.6875%
* Percentage of negative trades: 70.3125%
* Average trade size: 108.4551 EUR
* Average trade duration: 77.125 hours
.... All trades overview
```

As you can see this trading strategy is profitable with a growth rate of 17% on its closed trades.
When creating a trading strategy its also very important to run the strategy on a time range that was considered to be a market downturn for you selected
assets. This will help you determine if your trading strategy is robust enough to handle market downturns.

For bitcoin the period from 11-11-2021 to 11-11-2022 was considered to be a market downturn.
When running our trading strategy on this period we get the following results:

```bash
$ python backtest 2021-11-11 2022-11-11
====================Backtest report===============================
* Start date: 2021-11-11 00:00:00
* End date: 2022-11-11 00:00:00
* Number of days: 365
* Number of runs: 4381
====================Portfolio overview============================
* Number of orders: 130
* Initial balance: 400.0000 EUR
* Final balance: 356.0855 EUR
* Total net gain: -43.9145 EUR
* Total net gain percentage: -10.9786%
* Growth rate: -10.9786%
* Growth -43.9145 EUR
====================Positions overview========================
╭────────────┬──────────┬──────────────────┬──────────────┬───────────────┬───────────────────────────┬────────────────┬───────────────╮
│ Position   │   Amount │   Pending amount │   Cost (EUR) │   Value (EUR) │ Percentage of portfolio   │   Growth (EUR) │ Growth_rate   │
├────────────┼──────────┼──────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ EUR        │  356.086 │                0 │      356.086 │       356.086 │ 100.0000%                 │              0 │ 0.0000%       │
╰────────────┴──────────┴──────────────────┴──────────────┴───────────────┴───────────────────────────┴────────────────┴───────────────╯
====================Trades overview===========================
* Number of trades closed: 65
* Number of trades open: 0
* Percentage of positive trades: 29.230769230769234%
* Percentage of negative trades: 70.76923076923077%
* Average trade size: 89.5404 EUR
* Average trade duration: 59.96923076923077 hours
.... All trades overview
```

As you can see this trading strategy is not profitable with a profit rate of -4% on its closed trades.
We will try to improve it in the next section. The important thing to note here is that our trading strategy is not robust enough to handle market downturns.

## 4 Improving our trading strategy
In the previous section we saw that our trading bot was not profitable. In this section we will try to improve our trading strategy.
Whenever creating a trading bot you should always experiment with different metrics and parameters. In this section we will try to improve
our trading strategy by making the following changes:

- Adding stop losses on our open trades, so we can pre-emtively close our trades when the price drops below a certain price.
- Adding a trend line to our trading strategy, so we only sell when the price is below the trend line.
- Changing out fast moving average from a simple moving average to an exponential moving average, which will give more weight to the most recent prices.


First, we will add a trend line (100sma) and change the fast sma (simple moving average) to a fast ema (exponential moving average).

```python
class ImprovedGoldenCrossDeathCrossTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    market_data_sources = [
        "BTC/EUR-ohlcv",
        "BTC/EUR-ticker",
    ]
    symbols = ["BTC/EUR"]

    def apply_strategy(self, algorithm: Algorithm, market_data: dict):

        for symbol in self.symbols:
            target_symbol = symbol.split('/')[0]

            # Don't open a new order when we already have an open order
            if algorithm.has_open_orders(target_symbol):
                continue

            ohlcv_data = market_data[f"{symbol}-ohlcv"]
            df = pd.DataFrame(
                ohlcv_data,
                columns=['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']
            )
            fast = tp.sma(df["Close"].to_numpy(), period=9)
            # Changed fast sma to fast ema
            slow = tp.ema(df["Close"].to_numpy(), period=50)
            # Calculate trend line
            trend = tp.sma(df["Close"].to_numpy(), period=100)
            price = market_data[f"{symbol}-ticker"]["bid"]

            .... Remaining code
```

Finally, we change the sell and buy triggers:

```python
def apply_strategy(self, algorithm: Algorithm, market_data: dict):

    for symbol in self.symbols:
        target_symbol = symbol.split('/')[0]

        # Don't open a new order when we already have an open order
        if algorithm.has_open_orders(target_symbol):
            continue

        ohlcv_data = market_data[f"{symbol}-ohlcv"]
        df = pd.DataFrame(
            ohlcv_data,
            columns=['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']
        )
        fast = tp.sma(df["Close"].to_numpy(), period=9)
        # Changed fast sma to fast ema
        slow = tp.ema(df["Close"].to_numpy(), period=50)
        # Calculate trend line
        trend = tp.sma(df["Close"].to_numpy(), period=100)
        price = market_data[f"{symbol}-ticker"]["bid"]
        
        # Sell when crossunder with trend
        if algorithm.has_position(target_symbol) \
                and is_crossunder(fast, trend):
            algorithm.close_position(target_symbol)
            
        # Only buy when crossover
        elif not algorithm.has_position(target_symbol) \
                and is_crossover(fast, slow) \
            algorithm.create_limit_order(
                target_symbol=target_symbol,
                order_side=OrderSide.BUY,
                price=price,
                percentage_of_portfolio=25,
                precision=4
            )

        # Checking manual stopp losses with a 6% stop loss
        open_trades = algorithm.get_open_trades(target_symbol)

        for open_trade in open_trades:
            filtered_df = df[open_trade.opened_at <= df['Datetime']]
            close_prices = filtered_df['Close'].tolist()
            current_price = market_data[f"{symbol}-ticker"]

            if open_trade.is_manual_stop_loss_trigger(
                prices=close_prices,
                current_price=current_price["bid"],
                stop_loss_percentage=6
            ):
                algorithm.close_trade(open_trade)
```

When we run this trading strategy for the same time period as before
we get the following result:
```bash 
$ python backtest 2021-11-11 2022-11-11
====================Backtest report===============================
* Start date: 2021-11-11 00:00:00
* End date: 2022-11-11 00:00:00
* Number of days: 365
* Number of runs: 4381
====================Portfolio overview============================
* Number of orders: 34
* Initial balance: 400.0000 EUR
* Final balance: 378.3081 EUR
* Total net gain: -21.6919 EUR
* Total net gain percentage: -5.4230%
* Growth rate: -5.4230%
* Growth -21.6919 EUR
====================Positions overview========================
╭────────────┬──────────┬──────────────────┬──────────────┬───────────────┬───────────────────────────┬────────────────┬───────────────╮
│ Position   │   Amount │   Pending amount │   Cost (EUR) │   Value (EUR) │ Percentage of portfolio   │   Growth (EUR) │ Growth_rate   │
├────────────┼──────────┼──────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ EUR        │  378.308 │                0 │      378.308 │       378.308 │ 100.0000%                 │              0 │ 0.0000%       │
╰────────────┴──────────┴──────────────────┴──────────────┴───────────────┴───────────────────────────┴────────────────┴───────────────╯
====================Trades overview===========================
* Number of trades closed: 17
* Number of trades open: 0
* Percentage of positive trades: 11.76470588235294%
* Percentage of negative trades: 88.23529411764706%
* Average trade size: 95.9035 EUR
* Average trade duration: 69.29411764705883 hours
.... All trades overview
```

and for the favorable time period we get the following result:
```bash
$ python backtest.py 2023-01-01 2023-12-30
====================Backtest report===============================
* Start date: 2023-01-01 00:00:00
* End date: 2023-12-30 00:00:00
* Number of days: 363
* Number of runs: 4357
====================Portfolio overview============================
* Number of orders: 90
* Initial balance: 400.0000 EUR
* Final balance: 464.3659 EUR
* Total net gain: 64.3659 EUR
* Total net gain percentage: 16.0915%
* Growth rate: 16.0915%
* Growth 64.3659 EUR
====================Positions overview========================
╭────────────┬──────────┬──────────────────┬──────────────┬───────────────┬───────────────────────────┬────────────────┬───────────────╮
│ Position   │   Amount │   Pending amount │   Cost (EUR) │   Value (EUR) │ Percentage of portfolio   │   Growth (EUR) │ Growth_rate   │
├────────────┼──────────┼──────────────────┼──────────────┼───────────────┼───────────────────────────┼────────────────┼───────────────┤
│ EUR        │  464.366 │                0 │      464.366 │       464.366 │ 100.0000%                 │              0 │ 0.0000%       │
╰────────────┴──────────┴──────────────────┴──────────────┴───────────────┴───────────────────────────┴────────────────┴───────────────╯
====================Trades overview===========================
* Number of trades closed: 45
* Number of trades open: 0
* Percentage of positive trades: 31.11111111111111%
* Percentage of negative trades: 68.88888888888889%
* Average trade size: 109.6916 EUR
* Average trade duration: 123.28888888888889 hours
.... All trades overview
```


## 5 Deploying our trading bot
To deploy our trading bot we will create an azure function that will run our trading bot every 2 hours. Before we start,
please make sure you have the following installed and configured:

- You need to have a Microsoft Azure account to deploy the trading bot. You can create a free account [here](https://azure.microsoft.com/en-us/free/).
- You also need to have the Azure CLI installed. You can find the installation instructions[here](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli).
- You also need to have azure function core tools installed. You can find the installation instructions [here](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local?tabs=windows%2Cisolated-process%2Cnode-v4%2Cpython-v2%2Chttp-trigger%2Ccontainer-apps&pivots=programming-language-csharp#install-the-azure-functions-core-tools).
- Make sure you are logged in to Azure with the Azure CLI. You can do this by running the following command:
```bash
az login
```

First we create a new file called `host.json` with the following content:
```json
{
  "version": "2.0",
  "logging": {
    "applicationInsights": {
      "samplingSettings": {
        "isEnabled": true,
        "excludedTypes": "Request"
      }
    }
  },
  "extensionBundle": {
    "id": "Microsoft.Azure.Functions.ExtensionBundle",
    "version": "[4.*, 5.0.0)"
  }
}
```

Next we create a new file called `requirements.txt` with the following content:
```text
azure-functions
investing-algorithm-framework==2.0.4
tulipy==0.4.0
```

Next we create a file called `function_app.py` with the following content:
```python
import azure.functions as func
from investing_algorithm_framework import StatelessAction, \
    PortfolioConfiguration, MarketCredential

from app import app as trading_bot_app

trading_bot_app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="BITVAVO",
        trading_symbol="EUR"
    )
)
trading_bot_app.add_market_credential(
    MarketCredential( 
        market="BITVAVO",
        api_key="<YOUR_BITVAVO_API_KEY>",
        secret_key="<YOUR_BITVAVO_SECRET_KEY>"
    )
)
app = func.FunctionApp()


@app.timer_trigger(
    schedule="0 */2 * * * *",
    arg_name="myTimer",
    run_on_startup=True,
    use_monitor=False
)
def trading_bot_azure_function(myTimer: func.TimerRequest) -> None:
    trading_bot_app.run(payload={"ACTION": StatelessAction.RUN_STRATEGY.value})
```

Next we create a bash script called `create_resources.sh` and paste the
following content in it. This script will create the necessary resources on azure for our trading bot.

```bash
# Variables, you can change these if you want
resourceGroupName="Trading-bot-rg"
functionAppName="trading-bot-function-app"
storageAccountName="tradingbotstorageaccount"
location="westeurope"   

# Create a resource group
az group create --name $resourceGroupName --location $location

# Create a storage account
az storage account create --name $storageAccountName --location $location --resource-group $resourceGroupName --sku Standard_LRS

# Retrieve the storage account connection string
storageConnectionString=$(az storage account show-connection-string --name $storageAccountName --resource-group $resourceGroupName --query connectionString --output tsv)

# Create a consumption plan function app with Python 3.8
az functionapp create \
  --name $functionAppName \
  --resource-group $resourceGroupName \
  --storage-account $storageAccountName \
  --consumption-plan-location $location \
  --runtime python \
  --runtime-version 3.8 \
  --functions-version 3 \
  --os-type Linux \
  --disable-app-insights true

# Configure the storage connection string in the function app
az functionapp config appsettings set \
  --name $functionAppName \
  --resource-group $resourceGroupName \
  --settings AzureWebJobsStorage=$storageConnectionString
```

Nextup we can use the azure functools to deploy our trading bot to azure.
```bash
func azure functionapp publish trading-bot-function-app
```

If everything went well you should see all the resources in your azure portal
and the trading bot should be running every 2 hours on the azure function.

## 6 Conclusion
In this tutorial we have shown you how to build a trading bot with the investing algorithm framework.
We have also shown you how to test your trading bot and how to make some small improvements to let your trading bot perform better.
Finally, we have shown you how to deploy your trading bot to azure.

I hope you have enjoyed this tutorial and that you have learned something new. Please let me know if you have any questions or feedback. If
you would like to learn more about the investing algorithm framework you can check out the [documentation](https://investing-algorithm-framework.com/) also
you can check out the [Finterion](https://finterion.com) platform if you would like to use a trading bot, but do not want to build one yourself or if you would like to
make you trading bot available for other to use.

Also, don't forget to star the [investing algorithm framework](https://github.com/coding-kitties/investing-algorithm-framework) on github if you like it!

You can follow me on [twitter](https://twitter.com/mduyn) or connect with me on [linkedin](https://twitter.com/marcvanduyn). Also if you
would like to read upcoming blogs you can subscribe to my [medium account](https://medium.com/@marcvanduyn).
