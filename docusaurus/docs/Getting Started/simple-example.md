---
sidebar_position: 2
---

# Simple Example

Get started with a complete working example of a trading bot 
using the Investing Algorithm Framework.

## Overview

This example demonstrates how to create a sophisticated trading bot that uses technical analysis to trade Bitcoin. It showcases an RSI-EMA crossover strategy with comprehensive risk management, backtesting capabilities, and professional-grade features.

## Complete Example

Here's a complete working example that you can run right after installation:

> This example uses the `pyindicators` library for technical indicators. 
> Make sure to install it via pip:```pip install pyindicators```

```python
import logging.config
from typing import Dict, Any
from datetime import datetime, timezone

import pandas as pd
from pyindicators import ema, rsi, crossover, crossunder

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, PositionSize, create_app, RESOURCE_DIRECTORY, \
    BacktestDateRange, BacktestReport, TakeProfitRule, StopLossRule, \
    DEFAULT_LOGGING_CONFIG


# Use the framework provided logging configuration
logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)


class RSIEMACrossoverStrategy(TradingStrategy):
    algorithm_id = "RSI-EMA-Crossover-Strategy"
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    position_sizes = [
        PositionSize(
            symbol="BTC", percentage_of_portfolio=20.0
        ),
        PositionSize(
            symbol="ETH", percentage_of_portfolio=20.0
        )
    ]
    take_profits = [
        TakeProfitRule(
            symbol="BTC",
            percentage_threshold=10,
            trailing=True,
            sell_percentage=100
        ),
        TakeProfitRule(
            symbol="ETH",
            percentage_threshold=10,
            trailing=True,
            sell_percentage=100
        )
    ]
    stop_losses = [
        StopLossRule(
            symbol="BTC",
            percentage_threshold=5,
            trailing=False,
            sell_percentage=100
        ),
        StopLossRule(
            symbol="ETH",
            percentage_threshold=5,
            trailing=False,
            sell_percentage=100
        )
    ]

    def __init__(
        self,
        time_unit: TimeUnit,
        interval: int,
        market: str,
        rsi_time_frame: str,
        rsi_period: int,
        rsi_overbought_threshold,
        rsi_oversold_threshold,
        ema_time_frame,
        ema_short_period,
        ema_long_period,
        ema_cross_lookback_window: int = 10
    ):
        self.rsi_time_frame = rsi_time_frame
        self.rsi_period = rsi_period
        self.rsi_result_column = f"rsi_{self.rsi_period}"
        self.rsi_overbought_threshold = rsi_overbought_threshold
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.ema_time_frame = ema_time_frame
        self.ema_short_result_column = f"ema_{ema_short_period}"
        self.ema_long_result_column = f"ema_{ema_long_period}"
        self.ema_crossunder_result_column = "ema_crossunder"
        self.ema_crossover_result_column = "ema_crossover"
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.ema_cross_lookback_window = ema_cross_lookback_window
        data_sources = []

        for symbol in self.symbols:
            full_symbol = f"{symbol}/EUR"
            data_sources.append(
                DataSource(
                    identifier=f"{symbol}_rsi_data",
                    data_type=DataType.OHLCV,
                    time_frame=self.rsi_time_frame,
                    market=market,
                    symbol=full_symbol,
                    pandas=True,
                    window_size=800
                )
            )
            data_sources.append(
                DataSource(
                    identifier=f"{symbol}_ema_data",
                    data_type=DataType.OHLCV,
                    time_frame=self.ema_time_frame,
                    market=market,
                    symbol=full_symbol,
                    pandas=True,
                    window_size=800
                )
            )

        super().__init__(
            data_sources=data_sources, time_unit=time_unit, interval=interval
        )

    def _prepare_indicators(
        self,
        rsi_data,
        ema_data
    ):
        """
        Helper function to prepare the indicators 
        for the strategy. The indicators are calculated
        using the pyindicators library: https://github.com/coding-kitties/PyIndicators
        """
        ema_data = ema(
            ema_data,
            period=self.ema_short_period,
            source_column="Close",
            result_column=self.ema_short_result_column
        )
        ema_data = ema(
            ema_data,
            period=self.ema_long_period,
            source_column="Close",
            result_column=self.ema_long_result_column
        )
        # Detect crossover (short EMA crosses above long EMA)
        ema_data = crossover(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossover_result_column
        )
        # Detect crossunder (short EMA crosses below long EMA)
        ema_data = crossunder(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossunder_result_column
        )
        rsi_data = rsi(
            rsi_data,
            period=self.rsi_period,
            source_column="Close",
            result_column=self.rsi_result_column
        )

        return ema_data, rsi_data

    def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        """
        Generate buy signals based on the moving average crossover.

        data (Dict[str, Any]): Dictionary containing all the data for
            the strategy data sources.

        Returns:
            Dict[str, pd.Series]: A dictionary where keys are symbols and values
                are pandas Series indicating buy signals (True/False).
        """

        signals = {}

        for symbol in self.symbols:
            ema_data_identifier = f"{symbol}_ema_data"
            rsi_data_identifier = f"{symbol}_rsi_data"
            ema_data, rsi_data = self._prepare_indicators(
                data[ema_data_identifier].copy(),
                data[rsi_data_identifier].copy()
            )

            # crossover confirmed
            ema_crossover_lookback = ema_data[
                self.ema_crossover_result_column].rolling(
                window=self.ema_cross_lookback_window
            ).max().astype(bool)

            # use only RSI column
            rsi_oversold = rsi_data[self.rsi_result_column] \
                < self.rsi_oversold_threshold

            buy_signal = rsi_oversold & ema_crossover_lookback
            buy_signals = buy_signal.fillna(False).astype(bool)
            signals[symbol] = buy_signals
        return signals

    def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
        """
        Generate sell signals based on the moving average crossover.

        Args:
            data (Dict[str, Any]): Dictionary containing all the data for
                the strategy data sources.

        Returns:
            Dict[str, pd.Series]: A dictionary where keys are symbols and values
                are pandas Series indicating sell signals (True/False).
        """

        signals = {}
        for symbol in self.symbols:
            ema_data_identifier = f"{symbol}_ema_data"
            rsi_data_identifier = f"{symbol}_rsi_data"
            ema_data, rsi_data = self._prepare_indicators(
                data[ema_data_identifier].copy(),
                data[rsi_data_identifier].copy()
            )

            # Confirmed by crossover between short-term EMA and long-term EMA
            # within a given lookback window
            ema_crossunder_lookback = ema_data[
                self.ema_crossunder_result_column].rolling(
                window=self.ema_cross_lookback_window
            ).max().astype(bool)

            # use only RSI column
            rsi_overbought = rsi_data[self.rsi_result_column] \
               >= self.rsi_overbought_threshold

            # Combine both conditions
            sell_signal = rsi_overbought & ema_crossunder_lookback
            sell_signal = sell_signal.fillna(False).astype(bool)
            signals[symbol] = sell_signal
        return signals


if __name__ == "__main__":
    app = create_app()
    app.add_strategy(
        RSIEMACrossoverStrategy(
            time_unit=TimeUnit.HOUR,
            interval=2,
            market="bitvavo",
            rsi_time_frame="2h",
            rsi_period=14,
            rsi_overbought_threshold=70,
            rsi_oversold_threshold=30,
            ema_time_frame="2h",
            ema_short_period=12,
            ema_long_period=26,
            ema_cross_lookback_window=10
        )
    )

    # Market credentials for coinbase for both the portfolio connection and data sources will
    # be read from .env file, when not registering a market credential object in the app.
    app.add_market(
        market="bitvavo",
        trading_symbol="EUR",
    )
    backtest_range = BacktestDateRange(
        start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 6, 1, tzinfo=timezone.utc)
    )
    backtest = app.run_backtest(
        backtest_date_range=backtest_range, initial_amount=1000
    )
    report = BacktestReport(backtest)
    report.show(backtest_date_range=backtest_range, browser=True)
```

## Code Breakdown

Let's break down each part of this example:

### 1. Imports and Setup

```python
import logging.config
from typing import Dict, Any
from datetime import datetime, timezone

import pandas as pd
from pyindicators import ema, rsi, crossover, crossunder

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, PositionSize, create_app, RESOURCE_DIRECTORY, \
    BacktestDateRange, BacktestReport, TakeProfitRule, StopLossRule, \
    DEFAULT_LOGGING_CONFIG
```

- **pandas**: For data manipulation and analysis
- **pyindicators**: Technical analysis library for RSI and EMA calculations
- **Framework imports**: Core classes for strategy development, backtesting, and risk management

### 2. Logging Configuration

```python
logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)
```

- Sets up logging using the framework's default configuration for better debugging and monitoring

### 3. Trading Strategy Definition

```python
class RSIEMACrossoverStrategy(TradingStrategy):
    algorithm_id = "RSI-EMA-Crossover-Strategy"
    time_unit = TimeUnit.HOUR
    interval = 2
    symbols = ["BTC"]
    # ...
```

**Key Properties:**
- **algorithm_id**: Unique identifier for your strategy
- **time_unit**: The time unit for strategy execution (HOUR in this case)
- **interval**: How often to run the strategy (every 2 hours)
- **symbols**: List of trading symbols to monitor

### 4. Position Sizing and Risk Management

```python
position_sizes = [
    PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    PositionSize(symbol="ETH", percentage_of_portfolio=20.0)
]
take_profits = [
    TakeProfitRule(
        symbol="BTC",
        percentage_threshold=10,
        trailing=True,
        sell_percentage=100
    )
]
stop_losses = [
    StopLossRule(
        symbol="BTC",
        percentage_threshold=5,
        trailing=False,
        sell_percentage=100
    )
]
```

**Risk Management Features:**
- **Position Sizing**: Limits each position to 20% of portfolio
- **Take Profit**: Automatically sells when 10% profit is reached (with trailing)
- **Stop Loss**: Cuts losses at 5% drawdown to protect capital

### 5. Data Sources

```python
for symbol in self.symbols:
    full_symbol = f"{symbol}/EUR"
    data_sources.append(
        DataSource(
            identifier=f"{symbol}_rsi_data",
            data_type=DataType.OHLCV,
            time_frame=self.rsi_time_frame,
            market=market,
            symbol=full_symbol,
            pandas=True,
            window_size=800
        )
    )
    data_sources.append(
        DataSource(
            identifier=f"{symbol}_ema_data",
            data_type=DataType.OHLCV,
            time_frame=self.ema_time_frame,
            market=market,
            symbol=full_symbol,
            pandas=True,
            window_size=800
        )
    )
```

**Data Sources for Technical Analysis:**
- **RSI Data Source**: OHLCV data for RSI indicator calculation
- **EMA Data Source**: OHLCV data for moving average calculations  
- **window_size**: 800 candles for sufficient historical data
- **pandas**: Returns data as pandas DataFrame for easy analysis

### 6. Technical Indicators

```python
def _prepare_indicators(self, rsi_data, ema_data):
    # Calculate short and long EMAs
    ema_data = ema(ema_data, period=self.ema_short_period, 
                   source_column="Close", result_column=self.ema_short_result_column)
    ema_data = ema(ema_data, period=self.ema_long_period,
                   source_column="Close", result_column=self.ema_long_result_column)
    
    # Detect EMA crossovers
    ema_data = crossover(ema_data, first_column=self.ema_short_result_column,
                        second_column=self.ema_long_result_column,
                        result_column=self.ema_crossover_result_column)
    
    # Calculate RSI
    rsi_data = rsi(rsi_data, period=self.rsi_period,
                   source_column="Close", result_column=self.rsi_result_column)
```

**Technical Indicators Used:**
- **EMA (Exponential Moving Average)**: Short-term (12) and long-term (26) trends
- **RSI (Relative Strength Index)**: Momentum oscillator (14-period)
- **Crossover Detection**: Identifies when short EMA crosses above/below long EMA

### 7. Strategy Logic

```python
def generate_buy_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
    # Buy when RSI is oversold AND EMA crossover occurred recently
    rsi_oversold = rsi_data[self.rsi_result_column] < self.rsi_oversold_threshold
    ema_crossover_lookback = ema_data[self.ema_crossover_result_column].rolling(
        window=self.ema_cross_lookback_window).max().astype(bool)
    
    buy_signal = rsi_oversold & ema_crossover_lookback
    return buy_signal

def generate_sell_signals(self, data: Dict[str, Any]) -> Dict[str, pd.Series]:
    # Sell when RSI is overbought AND EMA crossunder occurred recently  
    rsi_overbought = rsi_data[self.rsi_result_column] >= self.rsi_overbought_threshold
    ema_crossunder_lookback = ema_data[self.ema_crossunder_result_column].rolling(
        window=self.ema_cross_lookback_window).max().astype(bool)
        
    sell_signal = rsi_overbought & ema_crossunder_lookback
    return sell_signal
```

**Trading Logic:**
- **Buy Signals**: Generated when RSI indicates oversold conditions (< 30) AND a recent EMA bullish crossover
- **Sell Signals**: Generated when RSI indicates overbought conditions (> 70) AND a recent EMA bearish crossover
- **Confirmation**: Uses lookback window to ensure signals are confirmed over multiple periods

### 8. Application Setup and Backtesting

```python
app = create_app()
app.add_strategy(
    RSIEMACrossoverStrategy(
        time_unit=TimeUnit.HOUR,
        interval=2,
        market="bitvavo",
        rsi_time_frame="2h",
        rsi_period=14,
        rsi_overbought_threshold=70,
        rsi_oversold_threshold=30,
        ema_time_frame="2h",
        ema_short_period=12,
        ema_long_period=26,
        ema_cross_lookback_window=10
    )
)

app.add_market(market="bitvavo", trading_symbol="EUR")

backtest_range = BacktestDateRange(
    start_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 6, 1, tzinfo=timezone.utc)
)
backtest = app.run_backtest(
    backtest_date_range=backtest_range, initial_amount=1000
)
report = BacktestReport(backtest)
report.show(backtest_date_range=backtest_range, browser=True)
```

- Creates the main application
- Configures the RSI-EMA strategy with specific parameters
- Sets up the market (Bitvavo exchange, EUR as base currency)
- Runs a backtest from January 2023 to June 2024 with €1000 initial capital
- Generates and displays a comprehensive performance report

## Running the Example

### Prerequisites

1. **Install the framework** (see [Installation](installation)):
   ```bash
   pip install investing-algorithm-framework
   ```

2. **Install pyindicators** for technical indicators:
   ```bash
   pip install pyindicators
   ```

3. **Install additional dependencies** (optional):
   ```bash
   pip install python-dotenv  # For environment variables
   ```

### Setup

1. **Create a new file** called `rsi_ema_strategy.py` and copy the example code above

2. **Create a `.env` file** (optional for this example):
   ```bash
   # .env file - only needed for live trading
   BITVAVO_API_KEY=your_api_key_here
   BITVAVO_API_SECRET=your_api_secret_here
   ```

3. **Run the strategy**:
   ```bash
   python rsi_ema_strategy.py
   ```

## Expected Output

When you run this example, the strategy will:

1. **Load historical data** for BTC/EUR from Bitvavo
2. **Calculate technical indicators** (RSI, EMA short, EMA long)
3. **Run the backtest** from January 2023 to June 2024
4. **Generate a comprehensive report** with performance metrics
5. **Open the report in your browser** showing:
   - Portfolio value over time
   - Trade history and signals
   - Performance metrics (Sharpe ratio, max drawdown, etc.)
   - Risk analysis and position sizes

You should see console output similar to:

```
2024-12-28 10:30:00,123 - INFO - Starting backtest application...
2024-12-28 10:30:00,456 - INFO - Registering strategy: RSI-EMA-Crossover-Strategy
2024-12-28 10:30:01,789 - INFO - Connected to Bitvavo market data
2024-12-28 10:30:02,123 - INFO - Loading historical data for BTC/EUR...
2024-12-28 10:30:05,456 - INFO - Calculating technical indicators...
2024-12-28 10:30:07,789 - INFO - Running backtest from 2023-01-01 to 2024-06-01...
2024-12-28 10:30:15,123 - INFO - Backtest completed. Opening performance report...
```

The browser will open showing detailed charts and metrics of your strategy's performance.

## Key Features Demonstrated

### 1. **Advanced Technical Analysis**
This example showcases:
- **Multiple Technical Indicators**: RSI and EMA calculations
- **Signal Confirmation**: Combining multiple indicators for robust signals
- **Lookback Windows**: Using historical confirmation for trade signals
- **Professional Indicators Library**: Integration with pyindicators

### 2. **Comprehensive Risk Management**
- **Position Sizing**: Automatic position size limits (20% per asset)
- **Take Profit Rules**: Trailing take profits at 10% gains
- **Stop Loss Protection**: 5% stop loss to limit downside risk
- **Portfolio Limits**: Built-in portfolio exposure controls

### 3. **Professional Backtesting**
- **Historical Data Analysis**: Tests strategy against real market data
- **Performance Metrics**: Comprehensive reporting with Sharpe ratio, drawdown analysis
- **Visual Reports**: Interactive charts and performance visualization
- **Realistic Simulation**: Accurate modeling of trading costs and slippage

### 4. **Production-Ready Structure**
- **Modular Design**: Clean separation of strategy logic and configuration
- **Logging Integration**: Professional logging for monitoring and debugging
- **Configurable Parameters**: Easy tuning of strategy parameters
- **Multiple Asset Support**: Framework for trading multiple cryptocurrencies

## Next Steps

Now that you have a working advanced strategy example, you can:

1. **Experiment with parameters** - Modify RSI periods, EMA periods, and thresholds
2. **Add more symbols** - Extend to trade ETH, ADA, and other cryptocurrencies  
3. **Implement live trading** - Add API credentials for live trading on Bitvavo
4. **Create custom indicators** - Develop your own technical analysis indicators
5. **Optimize strategy parameters** - Use the framework's optimization tools
6. **Add more sophisticated risk management** - Implement dynamic position sizing

Continue to [Application Setup](application-setup) to learn how to structure more complex trading applications, or jump to [Strategies](strategies) to learn about implementing more trading logic.

## Troubleshooting

### Common Issues

**ImportError: No module named 'investing_algorithm_framework'**
- Make sure you've installed the framework: `pip install investing-algorithm-framework`

**Connection errors**
- Check your internet connection
- Bitvavo might be temporarily unavailable

**No data received**
- The exchange might not support the requested symbol
- Try using a different timeframe or symbol

### Getting Help

If you encounter issues:
1. Check the logs for detailed error messages
2. Verify your Python version (3.8+ required)
3. Ensure all dependencies are installed

This example provides a solid foundation for building more sophisticated trading bots. Once you're comfortable with this advanced structure, you can explore the more advanced features covered in the rest of this documentation.
