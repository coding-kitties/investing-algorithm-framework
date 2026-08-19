---
sidebar_position: 3
---

# Multiple Market Data Sources

Learn how to use multiple data sources across different assets, timeframes, and markets in a single strategy.

## Multiple Assets

Use multiple `DataSource` objects to trade several assets simultaneously:

```python
from investing_algorithm_framework import (
    TradingStrategy, TimeUnit, DataSource, PositionSize,
    SignalSide, signals_from_column,
)

class MultiAssetStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 4
    symbols = ["BTC", "ETH", "ADA", "DOT"]
    trading_symbol = "EUR"

    data_sources = [
        DataSource(
            identifier="btc_4h",
            symbol="BTC/EUR",
            time_frame="4h",
            warmup_window=100,
            market="BITVAVO"
        ),
        DataSource(
            identifier="eth_4h",
            symbol="ETH/EUR",
            time_frame="4h",
            warmup_window=100,
            market="BITVAVO"
        ),
        DataSource(
            identifier="ada_4h",
            symbol="ADA/EUR",
            time_frame="4h",
            warmup_window=100,
            market="BITVAVO"
        ),
        DataSource(
            identifier="dot_4h",
            symbol="DOT/EUR",
            time_frame="4h",
            warmup_window=100,
            market="BITVAVO"
        )
    ]

    position_sizes = [
        PositionSize(symbol="BTC", percentage=0.25),
        PositionSize(symbol="ETH", percentage=0.25),
        PositionSize(symbol="ADA", percentage=0.25),
        PositionSize(symbol="DOT", percentage=0.25),
    ]

    def generate_signals(self, context, data):
        for symbol in self.symbols:
            identifier = f"{symbol.lower()}_4h"
            df = data[identifier]
            ma50 = df["Close"].rolling(50).mean()
            df["buy_signal"] = df["Close"] > ma50
            df["sell_signal"] = df["Close"] < ma50

            yield from signals_from_column(
                df, "buy_signal", side=SignalSide.OPEN_LONG, symbol=symbol,
            )
            yield from signals_from_column(
                df, "sell_signal", side=SignalSide.CLOSE_LONG, symbol=symbol,
            )
```

## Multiple Timeframes

Use multiple timeframes for more sophisticated analysis:

```python
class MultiTimeframeStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 1
    symbols = ["BTC"]
    trading_symbol = "EUR"

    data_sources = [
        # Daily for long-term trend
        DataSource(
            identifier="btc_daily",
            symbol="BTC/EUR",
            time_frame="1d",
            warmup_window=50,
            market="BITVAVO"
        ),
        # 4-hour for medium-term trend
        DataSource(
            identifier="btc_4h",
            symbol="BTC/EUR",
            time_frame="4h",
            warmup_window=100,
            market="BITVAVO"
        ),
        # Hourly for entry timing
        DataSource(
            identifier="btc_1h",
            symbol="BTC/EUR",
            time_frame="1h",
            warmup_window=200,
            market="BITVAVO"
        )
    ]

    position_sizes = [
        PositionSize(symbol="BTC", percentage=0.8),
    ]

    def _analyze_trend(self, df, ma_period=20):
        """Determine trend direction"""
        ma = df["Close"].rolling(ma_period).mean()
        current_price = df["Close"].iloc[-1]
        current_ma = ma.iloc[-1]

        if current_price > current_ma:
            return "bullish"
        elif current_price < current_ma:
            return "bearish"
        return "neutral"

    def generate_signals(self, context, data):
        daily_df = data["btc_daily"]
        h4_df = data["btc_4h"]
        h1_df = data["btc_1h"]

        # Check all timeframes
        daily_trend = self._analyze_trend(daily_df, ma_period=20)
        h4_trend = self._analyze_trend(h4_df, ma_period=20)

        # Generate hourly signals
        h1_ma = h1_df["Close"].rolling(20).mean()
        h1_cross_above = (h1_df["Close"] > h1_ma) & (h1_df["Close"].shift(1) <= h1_ma.shift(1))

        # Only buy when all timeframes align bullish
        h1_df["buy_signal"] = h1_cross_above.copy()

        if daily_trend != "bullish" or h4_trend != "bullish":
            h1_df["buy_signal"] = False

        # Sell on hourly MA cross below
        h1_df["sell_signal"] = (
            (h1_df["Close"] < h1_ma) & (h1_df["Close"].shift(1) >= h1_ma.shift(1))
        )

        yield from signals_from_column(
            h1_df, "buy_signal", side=SignalSide.OPEN_LONG, symbol="BTC",
        )
        yield from signals_from_column(
            h1_df, "sell_signal", side=SignalSide.CLOSE_LONG, symbol="BTC",
        )
```

## Mixing Markets

You can use different markets for different symbols in the same strategy:

```python
class MultiMarketStrategy(TradingStrategy):
    time_unit = TimeUnit.DAY
    interval = 1
    symbols = ["AAPL", "BTC"]
    trading_symbol = "USD"

    data_sources = [
        # Stocks from Yahoo Finance
        DataSource(
            identifier="aapl_daily",
            market="YAHOO",
            symbol="AAPL",
            time_frame="1d",
            warmup_window=200,
        ),
        # Crypto from Binance
        DataSource(
            identifier="btc_daily",
            market="BINANCE",
            symbol="BTC/USDT",
            time_frame="1d",
            warmup_window=200,
        ),
    ]
```

## Dynamic Data Source Creation

Create data sources programmatically for flexible strategies:

```python
class DynamicMultiAssetStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 4
    trading_symbol = "EUR"

    def __init__(
        self,
        symbols=None,
        market="BITVAVO",
        time_frame="4h",
        warmup_window=100,
        **kwargs
    ):
        if symbols is None:
            symbols = ["BTC", "ETH"]

        self.symbols = symbols
        self.market = market
        self._time_frame = time_frame

        # Dynamically create data sources
        data_sources = []
        position_sizes = []
        allocation = 0.8 / len(symbols)  # 80% total allocation

        for symbol in symbols:
            full_symbol = f"{symbol}/EUR"
            identifier = f"{symbol.lower()}_{time_frame}"

            data_sources.append(
                DataSource(
                    identifier=identifier,
                    symbol=full_symbol,
                    time_frame=time_frame,
                    warmup_window=warmup_window,
                    market=market
                )
            )

            position_sizes.append(
                PositionSize(symbol=symbol, percentage=allocation)
            )

        super().__init__(
            data_sources=data_sources,
            position_sizes=position_sizes,
            **kwargs
        )

    def generate_signals(self, context, data):
        for symbol in self.symbols:
            identifier = f"{symbol.lower()}_{self._time_frame}"
            df = data[identifier]
            ma20 = df["Close"].rolling(20).mean()
            df["buy_signal"] = df["Close"] > ma20
            df["sell_signal"] = df["Close"] < ma20

            yield from signals_from_column(
                df, "buy_signal", side=SignalSide.OPEN_LONG, symbol=symbol,
            )
            yield from signals_from_column(
                df, "sell_signal", side=SignalSide.CLOSE_LONG, symbol=symbol,
            )

# Usage
strategy = DynamicMultiAssetStrategy(
    symbols=["BTC", "ETH", "ADA", "DOT", "LINK"],
    market="BITVAVO",
    time_frame="4h",
    warmup_window=100
)
```

## Correlation Analysis

Use data from multiple assets to build correlation-based strategies:

```python
class CorrelationStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 4
    symbols = ["BTC"]
    trading_symbol = "EUR"

    data_sources = [
        DataSource(identifier="btc", symbol="BTC/EUR", time_frame="4h", warmup_window=100, market="BITVAVO"),
        DataSource(identifier="eth", symbol="ETH/EUR", time_frame="4h", warmup_window=100, market="BITVAVO"),
    ]

    def _calculate_correlation(self, df1, df2, window=20):
        """Calculate rolling correlation between two assets"""
        returns1 = df1["Close"].pct_change()
        returns2 = df2["Close"].pct_change()
        return returns1.rolling(window).corr(returns2)

    def generate_signals(self, context, data):
        btc_df = data["btc"]
        eth_df = data["eth"]

        # Calculate correlation
        correlation = self._calculate_correlation(btc_df, eth_df)

        # Buy BTC when correlation is high and ETH is rising
        eth_momentum = eth_df["Close"].pct_change(5)
        btc_df["buy_signal"] = (correlation > 0.7) & (eth_momentum > 0.02)

        ma = btc_df["Close"].rolling(20).mean()
        btc_df["sell_signal"] = btc_df["Close"] < ma

        yield from signals_from_column(
            btc_df, "buy_signal", side=SignalSide.OPEN_LONG, symbol="BTC",
        )
        yield from signals_from_column(
            btc_df, "sell_signal", side=SignalSide.CLOSE_LONG, symbol="BTC",
        )
```

## Data Source Patterns

### Pattern 1: Same Symbol, Multiple Timeframes

```python
data_sources = [
    DataSource(identifier="btc_1d", symbol="BTC/EUR", time_frame="1d", warmup_window=50, market="BITVAVO"),
    DataSource(identifier="btc_4h", symbol="BTC/EUR", time_frame="4h", warmup_window=100, market="BITVAVO"),
    DataSource(identifier="btc_1h", symbol="BTC/EUR", time_frame="1h", warmup_window=200, market="BITVAVO"),
]
```

### Pattern 2: Multiple Symbols, Same Timeframe

```python
data_sources = [
    DataSource(identifier="btc_4h", symbol="BTC/EUR", time_frame="4h", warmup_window=100, market="BITVAVO"),
    DataSource(identifier="eth_4h", symbol="ETH/EUR", time_frame="4h", warmup_window=100, market="BITVAVO"),
    DataSource(identifier="ada_4h", symbol="ADA/EUR", time_frame="4h", warmup_window=100, market="BITVAVO"),
]
```

## Data Provider Priority

When multiple data providers can serve the same `DataSource`, the framework uses priority to select the best one. Lower number = higher priority:

```python
from investing_algorithm_framework import create_app
from investing_algorithm_framework.infrastructure import (
    CCXTOHLCVDataProvider,
    PandasOHLCVDataProvider
)

app = create_app()

# Priority 1 = highest priority (used first)
app.add_data_provider(pandas_provider, priority=1)

# Priority 3 = lower priority (fallback)
app.add_data_provider(CCXTOHLCVDataProvider(), priority=3)
```

## Next Steps

- Learn about [Market Data Sources](market-data-sources) for supported markets and DataSource configuration
- Explore [External Data](external-data) to load CSV, JSON, or Parquet from URLs
- Check out [Trading Strategies](../Getting%20Started/strategies) for strategy implementation
