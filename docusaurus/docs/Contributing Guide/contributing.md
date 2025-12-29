---
sidebar_position: 1
---

# Contributing

Welcome to the Investing Algorithm Framework contributing guide! We appreciate your interest in contributing to the project.

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python 3.8+** installed
- **Git** for version control
- **Poetry** for dependency management (recommended)
- A **GitHub account**

### Setting Up Development Environment

1. **Fork the Repository**
   ```bash
   # Go to GitHub and fork the repository
   # https://github.com/coding-kitties/investing-algorithm-framework
   ```

2. **Clone Your Fork**
   ```bash
   git clone https://github.com/YOUR_USERNAME/investing-algorithm-framework.git
   cd investing-algorithm-framework
   ```

3. **Add Upstream Remote**
   ```bash
   git remote add upstream https://github.com/coding-kitties/investing-algorithm-framework.git
   ```

4. **Install Dependencies**
   ```bash
   # Using Poetry (recommended)
   poetry install --with dev,test
   poetry shell

   # Or using pip
   pip install -e .[dev,test]
   ```

5. **Install Pre-commit Hooks**
   ```bash
   pre-commit install
   ```

## Development Workflow

### Creating a Feature Branch

```bash
# Make sure you're on main and up to date
git checkout main
git pull upstream main

# Create a new feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/issue-description
```

### Making Changes

1. **Write Tests First** (TDD approach recommended)
   ```python
   # tests/test_your_feature.py
   import pytest
   from investing_algorithm_framework import YourNewFeature

   class TestYourNewFeature:
       def test_basic_functionality(self):
           feature = YourNewFeature()
           result = feature.do_something()
           assert result == expected_value
   ```

2. **Implement Your Feature**
   ```python
   # investing_algorithm_framework/your_module.py
   class YourNewFeature:
       def do_something(self):
           # Your implementation
           pass
   ```

3. **Run Tests**
   ```bash
   # Run specific tests
   pytest tests/test_your_feature.py

   # Run all tests
   pytest

   # Run with coverage
   pytest --cov=investing_algorithm_framework
   ```

4. **Check Code Quality**
   ```bash
   # Linting
   flake8 investing_algorithm_framework tests

   # Type checking
   mypy investing_algorithm_framework

   # Format code
   black investing_algorithm_framework tests
   isort investing_algorithm_framework tests
   ```

### Committing Changes

1. **Stage Your Changes**
   ```bash
   git add .
   ```

2. **Commit with Descriptive Message**
   ```bash
   git commit -m "feat: add new portfolio rebalancing strategy

   - Implement automatic portfolio rebalancing
   - Add threshold-based rebalancing triggers
   - Include comprehensive tests for edge cases
   - Update documentation with usage examples

   Fixes #123"
   ```

### Submitting a Pull Request

1. **Push Your Branch**
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request**
   - Go to GitHub and create a Pull Request
   - Use the PR template
   - Link related issues
   - Provide clear description of changes

3. **Address Review Feedback**
   - Make requested changes
   - Push additional commits to your branch
   - Respond to reviewer comments

## Contribution Types

### Bug Reports

When reporting bugs, please include:

```markdown
**Bug Description**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Create app with configuration X
2. Add strategy Y
3. Run backtest with parameters Z
4. See error

**Expected Behavior**
A clear description of what you expected to happen.

**Environment**
- OS: [e.g., macOS, Ubuntu 20.04]
- Python version: [e.g., 3.9.7]
- Framework version: [e.g., 1.2.3]

**Additional Context**
- Error logs
- Configuration files
- Screenshots (if applicable)
```

### Feature Requests

For feature requests, please provide:

```markdown
**Feature Description**
A clear description of the feature you'd like to see.

**Use Case**
Describe the problem this feature would solve.

**Proposed Solution**
If you have ideas on implementation, please share them.

**Alternatives Considered**
Any alternative solutions or workarounds you've considered.

**Additional Context**
Any other context, screenshots, or examples.
```

### Code Contributions

#### New Features

```python
# Example: Adding a new indicator

class RSIIndicator:
    """Relative Strength Index technical indicator."""
    
    def __init__(self, period: int = 14):
        """
        Initialize RSI indicator.
        
        Args:
            period: Number of periods for RSI calculation
        """
        self.period = period
        
    def calculate(self, prices: List[float]) -> List[float]:
        """
        Calculate RSI values.
        
        Args:
            prices: List of closing prices
            
        Returns:
            List of RSI values
            
        Raises:
            ValueError: If insufficient data points
        """
        if len(prices) < self.period + 1:
            raise ValueError(f"Need at least {self.period + 1} data points")
        
        # Implementation here
        pass
```

#### Documentation

```python
def create_trading_strategy(
    name: str,
    symbols: List[str],
    timeframe: str = "1d"
) -> TradingStrategy:
    """
    Create a new trading strategy.
    
    This function helps create a trading strategy with the specified
    parameters. The strategy will be configured to trade the given
    symbols on the specified timeframe.
    
    Args:
        name: Name of the trading strategy
        symbols: List of symbols to trade (e.g., ["BTC/USDT", "ETH/USDT"])
        timeframe: Trading timeframe (default: "1d")
        
    Returns:
        TradingStrategy: Configured trading strategy instance
        
    Example:
        >>> strategy = create_trading_strategy(
        ...     name="MA Crossover",
        ...     symbols=["BTC/USDT"],
        ...     timeframe="1h"
        ... )
        >>> app.add_strategy(strategy)
        
    Raises:
        ValueError: If invalid symbols or timeframe provided
    """
    # Implementation
    pass
```

## Code Style Guidelines

### Python Code Style

We follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) with some modifications:

```python
# Good: Clear, descriptive names
class MovingAverageStrategy(TradingStrategy):
    def __init__(self, short_period: int = 20, long_period: int = 50):
        self.short_period = short_period
        self.long_period = long_period
    
    def calculate_moving_average(self, prices: List[float], period: int) -> float:
        """Calculate simple moving average."""
        return sum(prices[-period:]) / period

# Bad: Unclear names, no type hints
class MAStrat:
    def __init__(self, s=20, l=50):
        self.s = s
        self.l = l
    
    def calc_ma(self, p, per):
        return sum(p[-per:]) / per
```

### Import Organization

```python
# Standard library imports
import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict

# Third-party imports
import pandas as pd
import numpy as np
from ccxt import Exchange

# Local imports
from investing_algorithm_framework.domain import TradingStrategy
from investing_algorithm_framework.infrastructure import CCXTOrderExecutor
```

### Error Handling

```python
# Good: Specific exceptions with helpful messages
def get_market_data(symbol: str, timeframe: str) -> pd.DataFrame:
    try:
        data = self.data_provider.get_data(symbol, timeframe)
        if not data:
            raise DataError(f"No data available for {symbol} on {timeframe}")
        return pd.DataFrame(data)
    except ConnectionError as e:
        raise DataError(f"Failed to fetch data for {symbol}: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error fetching {symbol} data: {e}")
        raise

# Bad: Broad exception handling
def get_market_data(symbol, timeframe):
    try:
        data = self.data_provider.get_data(symbol, timeframe)
        return pd.DataFrame(data)
    except:
        return None
```

## Testing Guidelines

### Unit Tests

```python
import pytest
from unittest.mock import Mock, patch
from investing_algorithm_framework import TradingStrategy

class TestTradingStrategy:
    def test_strategy_initialization(self):
        """Test strategy can be initialized with default parameters."""
        strategy = TradingStrategy()
        assert strategy is not None
        
    def test_strategy_with_custom_parameters(self):
        """Test strategy initialization with custom parameters."""
        strategy = TradingStrategy(risk_per_trade=0.02)
        assert strategy.risk_per_trade == 0.02
        
    @patch('investing_algorithm_framework.MarketDataProvider')
    def test_strategy_execution_with_mock_data(self, mock_data_provider):
        """Test strategy execution with mocked market data."""
        # Setup
        mock_data_provider.get_data.return_value = [
            {"open": 100, "high": 105, "low": 95, "close": 102}
        ]
        
        strategy = TradingStrategy()
        algorithm = Mock()
        
        # Execute
        strategy.apply_strategy(algorithm, mock_data_provider)
        
        # Assert
        mock_data_provider.get_data.assert_called()
        
    def test_strategy_handles_no_data(self):
        """Test strategy handles case when no market data is available."""
        strategy = TradingStrategy()
        algorithm = Mock()
        market_data = Mock()
        market_data.get_data.return_value = None
        
        # Should not raise exception
        strategy.apply_strategy(algorithm, market_data)
```

### Integration Tests

```python
class TestTradingIntegration:
    @pytest.fixture
    def app(self):
        """Create test app with minimal configuration."""
        from investing_algorithm_framework import create_app
        return create_app(config={'testing': True})
    
    def test_end_to_end_trading_flow(self, app):
        """Test complete trading flow from strategy to order execution."""
        # Add test strategy
        strategy = TestStrategy()
        app.add_strategy(strategy)
        
        # Add test data
        app.add_test_data("BTC/USDT", test_market_data)
        
        # Run backtest
        results = app.run_backtest(
            start_date="2023-01-01",
            end_date="2023-01-31"
        )
        
        # Verify results
        assert results.total_trades > 0
        assert results.final_portfolio_value > 0
```

### Performance Tests

```python
import pytest
import time

class TestPerformance:
    def test_strategy_execution_performance(self):
        """Test strategy executes within acceptable time limits."""
        strategy = TradingStrategy()
        algorithm = Mock()
        market_data = Mock()
        market_data.get_data.return_value = generate_large_dataset(10000)
        
        start_time = time.time()
        strategy.apply_strategy(algorithm, market_data)
        execution_time = time.time() - start_time
        
        # Should complete within 1 second for 10k data points
        assert execution_time < 1.0
        
    @pytest.mark.benchmark
    def test_backtest_performance(self, benchmark):
        """Benchmark backtest execution speed."""
        app = create_test_app()
        
        result = benchmark(
            app.run_backtest,
            start_date="2023-01-01",
            end_date="2023-12-31"
        )
        
        assert result.total_trades >= 0
```

## Documentation Standards

### Docstring Format

We use Google-style docstrings:

```python
def calculate_portfolio_metrics(
    portfolio_value: float,
    benchmark_value: float,
    risk_free_rate: float = 0.02
) -> Dict[str, float]:
    """
    Calculate portfolio performance metrics.
    
    This function calculates common portfolio performance metrics
    including Sharpe ratio, alpha, and beta relative to a benchmark.
    
    Args:
        portfolio_value: Current portfolio value in base currency
        benchmark_value: Current benchmark value
        risk_free_rate: Risk-free rate for Sharpe ratio calculation.
            Defaults to 2% (0.02).
            
    Returns:
        Dict containing calculated metrics:
            - sharpe_ratio: Risk-adjusted return metric
            - alpha: Excess return over benchmark
            - beta: Portfolio sensitivity to benchmark
            
    Raises:
        ValueError: If portfolio_value or benchmark_value is negative
        
    Example:
        >>> metrics = calculate_portfolio_metrics(10000, 9500, 0.025)
        >>> print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        Sharpe Ratio: 1.25
    """
    if portfolio_value < 0 or benchmark_value < 0:
        raise ValueError("Portfolio and benchmark values must be non-negative")
    
    # Implementation here
    return {
        "sharpe_ratio": 0.0,
        "alpha": 0.0,
        "beta": 0.0
    }
```

### README Updates

When adding new features, update relevant documentation:

```markdown
## New Portfolio Rebalancing Feature

The framework now supports automatic portfolio rebalancing:

```python
from investing_algorithm_framework import PortfolioRebalancer

# Configure rebalancing strategy
rebalancer = PortfolioRebalancer(
    target_weights={"BTC": 0.6, "ETH": 0.3, "ADA": 0.1},
    rebalance_threshold=0.05,  # 5% deviation triggers rebalance
    rebalance_frequency="weekly"
)

app.add_rebalancer(rebalancer)
```

This feature helps maintain target asset allocation automatically.
```

## Pull Request Process

### PR Template

```markdown
## Description
Brief description of changes and motivation.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)  
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] New tests added for new functionality
- [ ] All existing tests pass
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Code is properly commented
- [ ] Corresponding documentation updated
- [ ] No new warnings introduced

## Related Issues
Fixes #(issue number)
```

### Review Criteria

Pull requests will be reviewed for:

1. **Functionality**: Does it work as intended?
2. **Testing**: Are there adequate tests?
3. **Code Quality**: Is the code readable and maintainable?
4. **Documentation**: Is it properly documented?
5. **Performance**: Does it introduce performance regressions?
6. **Breaking Changes**: Are breaking changes properly documented?

## Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features, backwards compatible
- **PATCH**: Bug fixes, backwards compatible

### Changelog Format

```markdown
## [1.2.0] - 2024-01-15

### Added
- New portfolio rebalancing feature
- Support for additional exchanges (Kraken, Bitfinex)
- Advanced risk management tools

### Changed
- Improved performance of backtesting engine
- Updated API for strategy configuration

### Deprecated
- Old configuration format (will be removed in v2.0)

### Fixed
- Bug in order execution timing
- Memory leak in data provider
```

## Community Guidelines

### Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Help others learn and grow
- Follow project guidelines

### Getting Help

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community discussions
- **Documentation**: Check docs for answers first

### Recognition

Contributors will be recognized in:
- Project README
- Release notes
- Annual contributor highlights

Thank you for contributing to the Investing Algorithm Framework! 🚀
