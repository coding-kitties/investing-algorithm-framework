---

sidebar_position: 1

---

# Market data sources
Algorithmic trading needs quick access to real-time data and effective data manipulation for successful analysis. 
To meet these needs, the framework provides a data object that can be used in your trading strategies.

For data availability, we use a push-based approach. This means we send the desired information directly as 
an argument to each trading strategy handler function or trading strategy class. 
It's easy to use – just annotate your handler with the information you need.

Here is an example of a handler that uses the `TICKER` data object:

```python
# A ticker market data source for the BTC/EUR symbol on the bitvavo exchange
bitvavo_ticker_btc_eur = CCXTTickerMarketDataSource(
    identifier="BTC-ticker",
    market="BITVAVO",
    symbol="BTC/EUR",
)

class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.SECOND  
    interval = 5  
    market_data_sources = ["BTC-ticker"] # Registering the market data source by using its identifier

    def apply_strategy(self, algorithm: Algorithm, data: dict):
        print(data)
        
# Make sure to register your market data sources with the app
app.add_trading_strategy(MyTradingStrategy)
app.add_market_data_source(bitvavo_ticker_btc_eur)
```

By doing so your handler function parameter data will be assigned a data Object containing ticker for BTC/EUR from 
the bitvavo exchange under the key "BTC-ticker".

## Accessing data 
You can easily access the data object by using the `identifier` attribute of your MarketDataSource object.
The following code snippet shows how to access the data object:

:::tip
The data object that is passed in your trading strategy is a dictionary. This allows you to access multiple data objects
in your trading strategy. The key of the dictionary is the identifier of the market data source.
:::

```python
# A ticker market data source for the BTC/EUR symbol on the bitvavo exchange
bitvavo_ticker_btc_eur = CCXTTickerMarketDataSource(
    identifier="BTC-ticker",
    market="BITVAVO",
    symbol="BTC/EUR",
)

class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.SECOND  
    interval = 5  
    market_data_sources = ["BTC-ticker"] # Registering the market data source by using its identifier

    def apply_strategy(self, algorithm: Algorithm, data):
        ticker_data = data["BTC-ticker"] # Accessing the data object directly by using the identifier
        
# Make sure to register your market data sources with the app
app.add_trading_strategy(MyTradingStrategy)
app.add_market_data_source(bitvavo_ticker_btc_eur)
```


## CCXT market data sources
The framework comes out of the box with support for the [ccxt](https://github.com/ccxt/ccxt).
This allows you the use the following ccxt market data sources:

- CCXTTickerMarketDataSource
- CCXTOHLCVMarketDataSource
- CCXTOrderBookMarketDataSource

### CCXTTickerMarketDataSource
The CCXTTickerMarketDataSource is used to get the latest ticker data for a symbol. It is based
on the popular [ccxt](https://github.com/ccxt/ccxt) library.

```python
from investing_algorithm_framework import CCXTTickerMarketDataSource, TradingStrategy, \
    Algorithm, TimeUnit

# A ohlcv market data source for the BTC/EUR symbol on the BITVAVO exchange
bitvavo_ticker_btc_eur = CCXTTickerMarketDataSource(
    identifier="BTC-ticker",
    market="BITVAVO",
    symbol="BTC/EUR",
)

class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.SECOND # The time unit of the strategy
    interval = 5 # The interval of the strategy, runs every 5 seconds
    # Registering the market data source
    market_data_sources = [bitvavo_ticker_btc_eur]

    def apply_strategy(self, algorithm: Algorithm, market_data: Dict[str, Any]):
        print(market_data[bitvavo_ticker_btc_eur.get_identifier()])
```

### CCXTOHLCVMarketDataSource
The CCXTOHLCVMarketDataSource is used to get candle stick/OHLCV data for a symbol. It is based
on the popular [ccxt](https://github.com/ccxt/ccxt) library.

:::info
For ohlcv data you need to specify a start date, and/or an end date.
If you don't specify an end date, the framework will use the current date as the end date. The daterange between
the start and end date is used to determine the number of candlesticks in your ohlcv data. E.g. if you
specify a start date of `start_date=datetime.utcnow() - timedelta(days=17)` and a timeframe of 2h, the framework will
fetch 216 candlesticks (17 days * 12 candlesticks per day). Keep in mind that by leveraging a function like `datetime.utcnow()`
you will get the current date in UTC time everytime the market data source is used. This allows you to get the latest data
everytime the strategy runs.
:::

```python
from investing_algorithm_framework import CCXTOHLCVMarketDataSource, TradingStrategy, \
    Algorithm, TimeUnit

# A order book market data source for the BTC/EUR symbol on the BITVAVO exchange
bitvavo_btc_eur_ohlcv_2h = CCXTTickerMarketDataSource(
    identifier="BTC-ohlcv-2h",
    market="BITVAVO",
    symbol="BTC/EUR",
)

class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.SECOND # The time unit of the strategy
    interval = 5 # The interval of the strategy, runs every 5 seconds
    # Registering the market data source
    market_data_sources = [bitvavo_btc_eur_ohlcv_2h]

    def apply_strategy(self, algorithm: Algorithm, market_data: Dict[str, Any]):
        print(market_data[bitvavo_btc_eur_ohlcv_2h.get_identifier()])
```

### CCXTOrderBookMarketDataSource
The CCXTOrderBookMarketDataSource is used to get order book data for a symbol. It is based
on the popular [ccxt](https://github.com/ccxt/ccxt) library.


```python
from investing_algorithm_framework import CCXTOrderBookMarketDataSource, TradingStrategy, \
    Algorithm, TimeUnit

# A ticker market data source for the BTC/EUR symbol on the BITVAVO exchange
bitvavo_btc_eur_order_book = CCXTOrderBookMarketDataSource(
    identifier="BTC-order-book",
    market="BITVAVO",
    symbol="BTC/EUR",
)

class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.SECOND # The time unit of the strategy
    interval = 5 # The interval of the strategy, runs every 5 seconds
    # Registering the market data source
    market_data_sources = [bitvavo_btc_eur_order_book]

    def apply_strategy(self, algorithm: Algorithm, market_data: Dict[str, Any]):
        print(market_data[bitvavo_btc_eur_order_book.get_identifier()])
```

