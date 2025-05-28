---

sidebar_position: 2

---

# Multiple data sources
The framework allows you to configure multiple data sources for your trading strategies.
You can use this to combine different data sources. This allowes you to easily use different exchanges 
or brokers in your trading strategy.

A quick example of how to use multiple data sources in your trading strategy:
```python
# A ticker market data source for the BTC/EUR symbol on the bitvavo exchange
bitvavo_ticker_btc_eur = CCXTTickerMarketDataSource(
    identifier="BTC-ticker",
    market="BITVAVO",
    symbol="BTC/EUR",
)

# A ohlcv market data source for the BTC/EUR symbol on the BITVAVO exchange
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC-ohlcv",
    market="BITVAVO",
    symbol="BTC/EUR",
    timeframe="2h",
    start_date_func=lambda : datetime.utcnow() - timedelta(days=17)
)

class MyTradingStrategy(TradingStrategy):
    time_unit = TimeUnit.SECOND  
    interval = 5  
    market_data_sources = ["BTC-ticker", "BTC-ohlcv"] # Registering the market data sources by using their identifiers

    def apply_strategy(self, algorithm: Algorithm, data):
        ticker_data = data["BTC-ticker"] # Accessing the ticker data object directly by using the identifier
        ohlcv_data = data["BTC-ohlcv"] # Accessing the ohlcv data object directly by using the identifier
        
# Make sure to register your market data sources with the app
app.add_trading_strategy(MyTradingStrategy)
app.add_market_data_source(bitvavo_ticker_btc_eur)
app.add_market_data_source(bitvavo_btc_eur_ohlcv_2h)
```

