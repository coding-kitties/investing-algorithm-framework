---
---
# Backtesting

Backtesting is the process of testing a trading strategy on historical data to see how it would have performed in the past.
You can easily run backtests with the framework for various timeframes and data sources.

## Running a backtest

When you have created a trading strategy you can easily run a backtest in the following ways:

```python
import logging.config
from datetime import datetime, timedelta
from investing_algorithm_framework import (
    CCXTOHLCVMarketDataSource, CCXTTickerMarketDataSource, PortfolioConfiguration, create_app, pretty_print_backtest, BacktestDateRange, TimeUnit, TradingStrategy, OrderSide, DEFAULT_LOGGING_CONFIG, Context
)

logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)

bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR-ohlcv-2h",
    market="BINANCE",
    symbol="BTC/EUR",
    time_frame="2h",
    window_size=200
)

class ExampleStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2
    market_data_sources = [bitvavo_btc_eur_ohlcv_2h, bitvavo_btc_eur_ticker]

    def apply_strategy(self, context: Context, market_data):
        print("Running strategy")

app = create_app(name="Example strategy")
app.add_strategy(CrossOverStrategy)

# Add a portfolio configuration of 400 euro initial balance
app.add_portfolio_configuration(
    PortfolioConfiguration(
        market="BINANCE", trading_symbol="EUR", initial_balance=400,
    )
)

if __name__ == "__main__":
    end_date = datetime(2023, 12, 2)
    start_date = end_date - timedelta(days=100)
    date_range = BacktestDateRange(
        start_date=start_date,
        end_date=end_date
    )
    backtest_report = app.run_backtest(
        backtest_date_range=date_range, save_in_memory_strategies=True
    )
```


### Showing the backtest results

You can show the backtest results by using the `pretty_print_backtest` function. This will show you the backtest report in a nice format.

```python   
report = app.run_backtest(
    backtest_date_range=date_range, save_in_memory_strategies=True
)
pretty_print_backtest(report)
```

### Loading old backtest reports

You can load old backtest reports by using the `load_backtest_report` function. This will load the backtest 
report from the file system.

```python
from investing_algorithm_framework import load_backtest_reports

reports = load_backtest_reports(<path_to_backtest_reports_directory>)
```

### Evaluating backtest reports

You can evaluate backtest reports by using the `BacktestReportsEvaluation` class. This will evaluate the backtest

```python
from investing_algorithm_framework import BacktestReportsEvaluation, \
    pretty_print_backtest_reports_evaluation, load_backtest_reports

reports = load_backtest_reports(<path_to_backtest_reports_directory>)
evaluation = BacktestReportsEvaluation(reports)
pretty_print_backtest_reports_evaluation(evaluation)
```

### Saving the strategy

During the backtest, the framework will not automatically save the strategy. You can save the strategy 
by using the `save_strategy` parameter of the `run_backtest` function. By default, it will save all the strategies
that are in the `strategies` directory. If the directory where there strategies are located has a different name, you
can specify the directory name by using the `strategy_directory` parameter of the `run_backtest` function.

> The save_strategy parameter by default expects that you have the following directory structure:
> ```yaml
> .
> ├── app.py
> ├── requirements.txt
> ├── strategies
> │   ├── data_providers.py
> │   └── strategy.py
> ├── .gitignore
> ├── .env.example
> └── README.md
> ```

```python
backtest_report = app.run_backtest(backtest_date_range=date_range, save_strategy=True)
```

Use the `strategy_directory` parameter to specify the directory where the strategies are located.

```python
backtest_report = app.run_backtest(
    backtest_date_range=date_range, save_strategy=True, strategy_directory="my_strategies"
)
```

If you want to directly save the loaded-in strategies, you can use the `save_in_memory_strategies` parameter of the `run_backtest` function. This will save the strategies
that are loaded in memory. This is useful if you're running a backtest in a jupyter notebook where the strategy is defined in a code cell.

```python
backtest_report = app.run_backtest(
    backtest_date_range=date_range, save_strategy=True, save_in_memory_strategies=True
)
