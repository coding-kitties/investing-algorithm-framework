---
sidebar_position: 2
---

# Style Guide

This style guide ensures consistency and readability across the Investing Algorithm Framework codebase.

## Python Style Guidelines

### Code Formatting

We use **Black** for code formatting with the following configuration:

```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py38']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | _build
  | buck-out
  | build
  | dist
)/
'''
```

### Import Style

#### Import Order

1. Standard library imports
2. Related third-party imports  
3. Local application/library imports

```python
# Standard library
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

# Third-party
import numpy as np
import pandas as pd
import ccxt
from sqlalchemy import Column, Integer, String

# Local
from investing_algorithm_framework.domain import TradingStrategy
from investing_algorithm_framework.infrastructure import CCXTOrderExecutor
from investing_algorithm_framework.services import PortfolioService
```

#### Import Guidelines

```python
# Good: Explicit imports
from investing_algorithm_framework.domain import (
    TradingStrategy,
    BacktestDateRange,
    PortfolioConfiguration
)

# Avoid: Wildcard imports
from investing_algorithm_framework.domain import *

# Good: Relative imports for same package
from .portfolio_service import PortfolioService
from ..domain.models import Order

# Avoid: Long relative imports
from ....some.deep.nested.module import SomeClass
```

### Variable Naming

#### General Rules

```python
# Good: Descriptive names
portfolio_total_value = 10000.0
moving_average_period = 20
btc_current_price = 45000.0

# Bad: Abbreviated or unclear names
ptv = 10000.0
map = 20
bcp = 45000.0

# Good: Boolean variables
is_backtesting = True
has_open_positions = False
should_rebalance = True

# Bad: Ambiguous boolean names
backtesting = True
positions = False
rebalance = True
```

#### Class Naming

```python
# Good: PascalCase for classes
class TradingStrategy:
    pass

class MovingAverageCrossoverStrategy(TradingStrategy):
    pass

class CCXTDataProvider:
    pass

# Bad: Snake_case or unclear names
class trading_strategy:
    pass

class Strategy1:
    pass

class MAStrat:
    pass
```

#### Method and Function Naming

```python
class PortfolioManager:
    # Good: Verb-based method names
    def calculate_total_value(self) -> float:
        pass
    
    def get_positions(self) -> List[Position]:
        pass
    
    def create_buy_order(self, symbol: str, amount: float) -> Order:
        pass
    
    def is_position_open(self, symbol: str) -> bool:
        pass
    
    # Bad: Unclear or noun-based names
    def total(self) -> float:
        pass
    
    def positions(self) -> List[Position]:
        pass
    
    def order(self, symbol: str, amount: float) -> Order:
        pass
```

#### Constants

```python
# Good: UPPERCASE with underscores
DEFAULT_TIMEFRAME = "1d"
MAX_POSITION_SIZE = 0.25
API_RATE_LIMIT = 1200  # requests per minute
SUPPORTED_EXCHANGES = ["binance", "coinbase", "kraken"]

# Bad: Mixed case or unclear names
defaultTimeframe = "1d"
maxPos = 0.25
limit = 1200
exchanges = ["binance", "coinbase", "kraken"]
```

### Type Hints

#### Basic Type Hints

```python
from typing import Dict, List, Optional, Union
from datetime import datetime

def calculate_moving_average(
    prices: List[float], 
    period: int
) -> float:
    return sum(prices[-period:]) / period

def get_portfolio_value(
    positions: Dict[str, float],
    prices: Dict[str, float]
) -> Optional[float]:
    if not positions:
        return None
    return sum(positions[symbol] * prices.get(symbol, 0) 
               for symbol in positions)
```

#### Complex Type Hints

```python
from typing import Callable, TypeVar, Generic, Protocol

# Type variables
T = TypeVar('T')
StrategyType = TypeVar('StrategyType', bound='TradingStrategy')

# Generic classes
class DataProvider(Generic[T]):
    def get_data(self, symbol: str) -> T:
        pass

# Protocols for structural typing
class Tradeable(Protocol):
    def get_current_price(self) -> float: ...
    def create_order(self, side: str, amount: float) -> Order: ...

# Complex function signatures
def backtest_strategy(
    strategy: TradingStrategy,
    data_provider: DataProvider[pd.DataFrame],
    date_range: BacktestDateRange,
    callback: Optional[Callable[[BacktestRun], None]] = None
) -> BacktestResults:
    pass
```

### Documentation Style

#### Class Documentation

```python
class MovingAverageStrategy(TradingStrategy):
    """
    Trading strategy based on moving average crossover signals.
    
    This strategy generates buy signals when a short-term moving average
    crosses above a long-term moving average, and sell signals when the
    short-term average crosses below the long-term average.
    
    Attributes:
        short_period: Number of periods for short moving average
        long_period: Number of periods for long moving average
        symbol: Trading symbol to apply strategy to
        
    Example:
        >>> strategy = MovingAverageStrategy(
        ...     short_period=20,
        ...     long_period=50,
        ...     symbol="BTC/USDT"
        ... )
        >>> app.add_strategy(strategy)
    """
    
    def __init__(
        self, 
        short_period: int = 20, 
        long_period: int = 50,
        symbol: str = "BTC/USDT"
    ):
        """
        Initialize the moving average strategy.
        
        Args:
            short_period: Period for short moving average. Must be less 
                than long_period. Defaults to 20.
            long_period: Period for long moving average. Must be greater 
                than short_period. Defaults to 50.
            symbol: Trading symbol to monitor. Defaults to "BTC/USDT".
            
        Raises:
            ValueError: If short_period >= long_period
            ValueError: If periods are not positive integers
        """
        if short_period >= long_period:
            raise ValueError("Short period must be less than long period")
        
        if short_period <= 0 or long_period <= 0:
            raise ValueError("Periods must be positive integers")
            
        self.short_period = short_period
        self.long_period = long_period
        self.symbol = symbol
```

#### Function Documentation

```python
def calculate_sharpe_ratio(
    returns: List[float], 
    risk_free_rate: float = 0.02,
    periods_per_year: int = 252
) -> float:
    """
    Calculate the Sharpe ratio for a series of returns.
    
    The Sharpe ratio measures risk-adjusted return by comparing the excess
    return of an investment over a risk-free rate to the volatility of the
    investment.
    
    Args:
        returns: List of periodic returns (e.g., daily returns)
        risk_free_rate: Annual risk-free rate. Defaults to 2% (0.02).
        periods_per_year: Number of return periods per year. Defaults to
            252 (trading days).
            
    Returns:
        The Sharpe ratio as a float. Higher values indicate better
        risk-adjusted returns.
        
    Raises:
        ValueError: If returns list is empty
        ValueError: If standard deviation is zero (no volatility)
        
    Example:
        >>> daily_returns = [0.01, -0.02, 0.015, 0.008, -0.005]
        >>> sharpe = calculate_sharpe_ratio(daily_returns, 0.025)
        >>> print(f"Sharpe Ratio: {sharpe:.2f}")
        Sharpe Ratio: 1.25
        
    Note:
        This function assumes the returns are already in decimal format
        (e.g., 0.01 for 1% return).
    """
    if not returns:
        raise ValueError("Returns list cannot be empty")
    
    mean_return = sum(returns) / len(returns)
    std_return = (sum((r - mean_return) ** 2 for r in returns) / len(returns)) ** 0.5
    
    if std_return == 0:
        raise ValueError("Cannot calculate Sharpe ratio with zero volatility")
    
    # Annualize the Sharpe ratio
    excess_return = mean_return - (risk_free_rate / periods_per_year)
    annualized_excess_return = excess_return * periods_per_year
    annualized_volatility = std_return * (periods_per_year ** 0.5)
    
    return annualized_excess_return / annualized_volatility
```

### Error Handling Style

#### Exception Hierarchy

```python
# Base framework exception
class InvestingAlgorithmFrameworkError(Exception):
    """Base exception for all framework-related errors."""
    pass

# Domain-specific exceptions
class TradingError(InvestingAlgorithmFrameworkError):
    """Base exception for trading-related errors."""
    pass

class OrderError(TradingError):
    """Exception raised for order-related errors."""
    pass

class InsufficientFundsError(OrderError):
    """Exception raised when insufficient funds for order."""
    pass

class DataError(InvestingAlgorithmFrameworkError):
    """Exception raised for data-related errors."""
    pass

class ConnectionError(DataError):
    """Exception raised for connection-related errors."""
    pass
```

#### Exception Usage

```python
def create_buy_order(
    self, 
    symbol: str, 
    amount: float,
    price: Optional[float] = None
) -> Order:
    """
    Create a buy order for the specified symbol and amount.
    
    Args:
        symbol: Trading symbol (e.g., "BTC/USDT")
        amount: Amount to buy in base currency
        price: Limit price (optional, uses market price if None)
        
    Returns:
        Created order object
        
    Raises:
        ValueError: If amount is not positive
        InsufficientFundsError: If account balance is insufficient
        ConnectionError: If exchange connection fails
    """
    # Input validation
    if amount <= 0:
        raise ValueError(f"Order amount must be positive, got {amount}")
    
    if not symbol:
        raise ValueError("Symbol cannot be empty")
    
    try:
        # Check available balance
        balance = self._get_available_balance()
        if balance < amount:
            raise InsufficientFundsError(
                f"Insufficient balance: {balance} < {amount}"
            )
        
        # Create order
        order = self._create_order_on_exchange(symbol, amount, price)
        return order
        
    except ConnectionError as e:
        # Re-raise connection errors with context
        raise ConnectionError(
            f"Failed to create order for {symbol}: {e}"
        ) from e
    
    except Exception as e:
        # Log unexpected errors and re-raise
        logger.error(f"Unexpected error creating order: {e}", exc_info=True)
        raise TradingError(f"Failed to create buy order: {e}") from e
```

### Logging Style

#### Logger Setup

```python
import logging

# Good: Module-level logger
logger = logging.getLogger(__name__)

class TradingStrategy:
    def __init__(self):
        # Good: Class-specific logger
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def apply_strategy(self, algorithm, market_data):
        self.logger.info("Executing trading strategy")
        
        try:
            current_price = market_data.get_last_price("BTC/USDT")
            self.logger.debug(f"Current BTC price: ${current_price:.2f}")
            
            # Strategy logic here
            
        except Exception as e:
            self.logger.error(f"Strategy execution failed: {e}", exc_info=True)
            raise
```

#### Logging Messages

```python
# Good: Informative log messages
logger.info("Starting portfolio rebalancing", extra={
    'portfolio_value': portfolio.total_value,
    'target_weights': target_weights,
    'current_weights': current_weights
})

logger.warning(
    "Position size exceeds risk limit",
    extra={
        'symbol': symbol,
        'position_size': position_size,
        'risk_limit': risk_limit,
        'portfolio_percentage': position_size / portfolio.total_value
    }
)

# Bad: Vague or missing information
logger.info("Rebalancing")
logger.warning("Risk limit exceeded")

# Good: Structured logging for production
logger.info("Order executed", extra={
    'event_type': 'order_filled',
    'order_id': order.id,
    'symbol': order.symbol,
    'side': order.side,
    'amount': order.amount,
    'price': order.price,
    'timestamp': datetime.utcnow().isoformat()
})
```

## Testing Style

### Test Organization

```python
# tests/test_trading_strategy.py
import pytest
from unittest.mock import Mock, patch
from investing_algorithm_framework import TradingStrategy

class TestTradingStrategy:
    """Test suite for TradingStrategy class."""
    
    @pytest.fixture
    def strategy(self):
        """Fixture providing a basic strategy instance."""
        return TradingStrategy()
    
    @pytest.fixture
    def mock_market_data(self):
        """Fixture providing mock market data."""
        mock_data = Mock()
        mock_data.get_last_price.return_value = 50000.0
        mock_data.get_data.return_value = [
            {"open": 49000, "high": 51000, "low": 48000, "close": 50000}
        ]
        return mock_data
    
    def test_strategy_initialization(self, strategy):
        """Test strategy can be initialized with default parameters."""
        assert strategy is not None
        assert hasattr(strategy, 'apply_strategy')
    
    def test_strategy_with_market_data(self, strategy, mock_market_data):
        """Test strategy execution with mock market data."""
        algorithm = Mock()
        
        # Should not raise exception
        strategy.apply_strategy(algorithm, mock_market_data)
        
        # Verify market data was accessed
        mock_market_data.get_last_price.assert_called()
    
    @pytest.mark.parametrize("price,expected_signal", [
        (45000, "buy"),
        (55000, "sell"),
        (50000, "hold")
    ])
    def test_strategy_signals_at_different_prices(
        self, 
        strategy, 
        price, 
        expected_signal
    ):
        """Test strategy generates correct signals at different price levels."""
        # Test implementation here
        pass
    
    def test_strategy_handles_missing_data(self, strategy):
        """Test strategy handles case when market data is unavailable."""
        algorithm = Mock()
        market_data = Mock()
        market_data.get_last_price.return_value = None
        
        # Should handle gracefully without crashing
        strategy.apply_strategy(algorithm, market_data)
    
    def test_strategy_error_handling(self, strategy):
        """Test strategy handles exceptions in market data access."""
        algorithm = Mock()
        market_data = Mock()
        market_data.get_last_price.side_effect = ConnectionError("Network error")
        
        with pytest.raises(ConnectionError):
            strategy.apply_strategy(algorithm, market_data)
```

### Assertion Style

```python
# Good: Clear, specific assertions
def test_portfolio_value_calculation():
    portfolio = Portfolio()
    portfolio.add_position("BTC", 0.1, 50000)
    portfolio.add_position("ETH", 2.0, 3000)
    
    expected_value = (0.1 * 50000) + (2.0 * 3000)
    actual_value = portfolio.calculate_total_value()
    
    assert actual_value == expected_value
    assert portfolio.get_position_count() == 2

# Good: Using pytest.approx for floating point comparisons
def test_sharpe_ratio_calculation():
    returns = [0.01, -0.02, 0.015, 0.008, -0.005]
    sharpe = calculate_sharpe_ratio(returns, risk_free_rate=0.02)
    
    assert sharpe == pytest.approx(1.25, abs=0.01)

# Good: Testing exception messages
def test_invalid_order_amount():
    portfolio = Portfolio()
    
    with pytest.raises(ValueError, match="Order amount must be positive"):
        portfolio.create_buy_order("BTC/USDT", -100)
```

## Configuration Style

### Environment Configuration

```python
# config/development.py
class DevelopmentConfig:
    """Development environment configuration."""
    
    DEBUG = True
    TESTING = False
    
    # Database
    DATABASE_URI = "sqlite:///dev.db"
    
    # Logging
    LOG_LEVEL = "DEBUG"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Trading
    PAPER_TRADING = True
    INITIAL_BALANCE = 10000.0
    
    # API Keys (should be loaded from environment)
    EXCHANGE_API_KEY = os.getenv("DEV_EXCHANGE_API_KEY")
    EXCHANGE_API_SECRET = os.getenv("DEV_EXCHANGE_API_SECRET")

# config/production.py  
class ProductionConfig:
    """Production environment configuration."""
    
    DEBUG = False
    TESTING = False
    
    # Database
    DATABASE_URI = os.getenv("DATABASE_URI")
    
    # Logging
    LOG_LEVEL = "INFO" 
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
    
    # Trading
    PAPER_TRADING = False
    INITIAL_BALANCE = float(os.getenv("INITIAL_BALANCE", "1000"))
    
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY")
    EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY")
    EXCHANGE_API_SECRET = os.getenv("EXCHANGE_API_SECRET")
```

### YAML Configuration Style

```yaml
# config.yaml
app:
  name: "Trading Bot"
  version: "1.0.0"
  environment: "production"

database:
  uri: "${DATABASE_URI}"
  pool_size: 10
  max_overflow: 20

exchanges:
  binance:
    api_key: "${BINANCE_API_KEY}"
    api_secret: "${BINANCE_API_SECRET}"
    sandbox: false
    rate_limit: 1200
    
portfolio:
  initial_balance: 10000.0
  trading_symbol: "USDT"
  max_position_size: 0.25
  risk_per_trade: 0.02

strategies:
  - name: "MA Crossover"
    class: "MovingAverageStrategy"
    parameters:
      short_period: 20
      long_period: 50
      symbols: ["BTC/USDT", "ETH/USDT"]

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  handlers:
    - type: "file"
      filename: "logs/trading.log"
      max_size: "10MB"
      backup_count: 5
    - type: "console"
      stream: "stdout"
```

## File Organization

### Directory Structure

```
investing_algorithm_framework/
├── __init__.py
├── app/                    # Application layer
│   ├── __init__.py
│   ├── app.py
│   ├── algorithm/
│   ├── analysis/
│   └── strategy/
├── domain/                 # Domain models and business logic
│   ├── __init__.py
│   ├── models/
│   ├── services/
│   └── exceptions/
├── infrastructure/         # External integrations
│   ├── __init__.py
│   ├── exchanges/
│   ├── data_providers/
│   └── databases/
├── cli/                   # Command-line interface
│   ├── __init__.py
│   └── commands/
└── utils/                 # Utility functions
    ├── __init__.py
    ├── datetime_utils.py
    └── math_utils.py

tests/
├── __init__.py
├── unit/
├── integration/
├── fixtures/
└── conftest.py

docs/
├── api/
├── guides/
└── examples/

examples/
├── basic_trading_bot.py
├── advanced_strategies/
└── data_analysis/
```

### Module Structure

```python
# investing_algorithm_framework/domain/models/order.py
"""
Order domain model.

This module contains the Order class and related enums for representing
trading orders within the framework.
"""

from enum import Enum
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

__all__ = ['Order', 'OrderStatus', 'OrderSide', 'OrderType']


class OrderStatus(Enum):
    """Enumeration of possible order statuses."""
    PENDING = "pending"
    OPEN = "open" 
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderSide(Enum):
    """Enumeration of order sides."""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Enumeration of order types."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


@dataclass
class Order:
    """
    Represents a trading order.
    
    This class encapsulates all information about a trading order,
    including its type, status, and execution details.
    
    Attributes:
        id: Unique identifier for the order
        symbol: Trading pair symbol (e.g., "BTC/USDT")
        side: Order side (buy or sell)
        type: Order type (market, limit, etc.)
        amount: Order amount in base currency
        price: Order price (None for market orders)
        status: Current order status
        created_at: Order creation timestamp
        updated_at: Last update timestamp
    """
    id: str
    symbol: str
    side: OrderSide
    type: OrderType
    amount: float
    price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize timestamps if not provided."""
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = self.created_at
```

## Git Commit Style

### Commit Message Format

```
<type>(<scope>): <description>

<body>

<footer>
```

### Types

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, etc.)
- **refactor**: Code refactoring
- **test**: Adding or updating tests
- **chore**: Maintenance tasks

### Examples

```bash
feat(portfolio): add automatic rebalancing functionality

Implement automatic portfolio rebalancing based on target weights.
The rebalancer monitors position sizes and triggers rebalancing
when positions deviate beyond the configured threshold.

Features:
- Configurable target weights per asset
- Customizable rebalancing threshold
- Support for scheduled rebalancing
- Comprehensive logging of rebalancing actions

Closes #123

fix(orders): handle exchange connection timeouts gracefully

Previously, connection timeouts during order placement would crash
the application. Now timeouts are caught and orders are retried
with exponential backoff.

- Add retry logic with exponential backoff
- Improve error messages for timeout scenarios
- Add comprehensive tests for timeout handling

Fixes #456

docs(api): update strategy creation examples

Update the strategy creation documentation to include examples
of the new portfolio rebalancing features and improved error
handling patterns.

test(integration): add end-to-end backtesting tests

Add comprehensive integration tests that verify the complete
backtesting workflow from strategy creation to results analysis.

- Test multiple strategies simultaneously
- Verify correct portfolio calculations
- Test error handling in edge cases
```

Following these style guidelines ensures that the codebase remains consistent, readable, and maintainable as the project grows and more contributors join the effort.
