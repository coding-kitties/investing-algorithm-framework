---
sidebar_position: 8
---

# Tasks

Learn how to create and schedule automated tasks to enhance your trading system.

## Overview

Tasks are automated functions that run independently of your trading strategies. They can be used for maintenance, data collection, reporting, monitoring, and other background operations that support your trading system.

## Creating Tasks

### Basic Task Structure

```python
from investing_algorithm_framework import Task

class DataCleanupTask(Task):
    
    def __init__(self):
        super().__init__(
            name="data_cleanup",
            interval="daily",  # Run daily
            time="02:00"      # Run at 2 AM
        )
    
    def run(self, algorithm):
        """Task execution logic"""
        print("Running data cleanup task...")
        
        # Cleanup old data
        self.cleanup_old_market_data()
        
        # Compact database
        self.compact_database()
        
        print("Data cleanup completed")
    
    def cleanup_old_market_data(self):
        # Implementation for data cleanup
        pass
    
    def compact_database(self):
        # Implementation for database optimization
        pass
```

### Registering Tasks

```python
from investing_algorithm_framework import create_app

app = create_app()

# Register the task
app.add_task(DataCleanupTask())

# Start the app (tasks will run automatically)
app.start()
```

## Task Scheduling

### Schedule Types

**Fixed Intervals:**
```python
# Run every 5 minutes
class MarketDataTask(Task):
    def __init__(self):
        super().__init__(
            name="market_data_collection",
            interval="5m"
        )

# Run every hour
class PortfolioReportTask(Task):
    def __init__(self):
        super().__init__(
            name="portfolio_report", 
            interval="1h"
        )

# Run daily
class BackupTask(Task):
    def __init__(self):
        super().__init__(
            name="daily_backup",
            interval="daily",
            time="23:30"
        )
```

**Cron-style Scheduling:**
```python
class WeeklyReportTask(Task):
    def __init__(self):
        super().__init__(
            name="weekly_report",
            cron="0 9 * * MON"  # Every Monday at 9 AM
        )

class MonthlyRebalanceTask(Task):
    def __init__(self):
        super().__init__(
            name="monthly_rebalance",
            cron="0 0 1 * *"  # First day of each month
        )
```

## Common Task Examples

### Market Data Collection

```python
class MarketDataCollector(Task):
    
    def __init__(self, symbols, data_provider):
        super().__init__(
            name="market_data_collector",
            interval="1m"  # Collect every minute
        )
        self.symbols = symbols
        self.data_provider = data_provider
    
    def run(self, algorithm):
        """Collect market data for specified symbols"""
        
        for symbol in self.symbols:
            try:
                # Fetch latest data
                data = self.data_provider.get_latest_data(symbol)
                
                # Store in database
                algorithm.store_market_data(symbol, data)
                
                print(f"Collected data for {symbol}")
                
            except Exception as e:
                print(f"Failed to collect data for {symbol}: {e}")
```

### Portfolio Monitoring

```python
class PortfolioMonitor(Task):
    
    def __init__(self, alert_manager):
        super().__init__(
            name="portfolio_monitor",
            interval="5m"
        )
        self.alert_manager = alert_manager
    
    def run(self, algorithm):
        """Monitor portfolio health and send alerts"""
        
        portfolio = algorithm.get_portfolio()
        positions = algorithm.get_positions()
        
        # Check total portfolio value
        total_value = portfolio.get_total_value()
        initial_value = portfolio.get_initial_value()
        
        pnl_percentage = (total_value - initial_value) / initial_value * 100
        
        # Alert on significant changes
        if pnl_percentage < -10:
            self.alert_manager.send_alert(
                f"Portfolio down {abs(pnl_percentage):.2f}%",
                severity="WARNING"
            )
        elif pnl_percentage > 20:
            self.alert_manager.send_alert(
                f"Portfolio up {pnl_percentage:.2f}%", 
                severity="INFO"
            )
        
        # Check individual positions
        self.check_position_alerts(positions)
    
    def check_position_alerts(self, positions):
        """Check for position-specific alerts"""
        
        for position in positions:
            # Alert on large positions
            if position.current_value > 5000:
                print(f"Large position alert: {position.symbol} = ${position.current_value:.2f}")
```

### Performance Reporting

```python
class PerformanceReporter(Task):
    
    def __init__(self, report_email=None):
        super().__init__(
            name="performance_reporter",
            interval="daily",
            time="18:00"  # 6 PM daily
        )
        self.report_email = report_email
    
    def run(self, algorithm):
        """Generate and send daily performance report"""
        
        # Calculate daily metrics
        daily_metrics = self.calculate_daily_metrics(algorithm)
        
        # Generate report
        report = self.generate_report(daily_metrics)
        
        # Send report
        if self.report_email:
            self.send_report_email(report)
        
        print("Daily performance report generated")
    
    def calculate_daily_metrics(self, algorithm):
        """Calculate daily performance metrics"""
        
        portfolio = algorithm.get_portfolio()
        trades = algorithm.get_trades()
        
        # Get today's trades
        today = datetime.now().date()
        today_trades = [
            t for t in trades 
            if t.created_at.date() == today
        ]
        
        metrics = {
            "portfolio_value": portfolio.get_total_value(),
            "daily_trades": len(today_trades),
            "daily_volume": sum(t.cost for t in today_trades),
            "daily_fees": sum(t.fee for t in today_trades),
            "open_positions": len(algorithm.get_positions())
        }
        
        return metrics
    
    def generate_report(self, metrics):
        """Generate formatted report"""
        
        report = f"""
        Daily Trading Report - {datetime.now().strftime('%Y-%m-%d')}
        =====================================================
        
        Portfolio Value: ${metrics['portfolio_value']:,.2f}
        
        Daily Activity:
        - Trades: {metrics['daily_trades']}
        - Volume: ${metrics['daily_volume']:,.2f}
        - Fees: ${metrics['daily_fees']:,.2f}
        - Open Positions: {metrics['open_positions']}
        
        Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        return report
```

### Risk Management

```python
class RiskManager(Task):
    
    def __init__(self, max_drawdown=0.15, max_position_size=0.1):
        super().__init__(
            name="risk_manager",
            interval="1m"  # Check risk every minute
        )
        self.max_drawdown = max_drawdown
        self.max_position_size = max_position_size
    
    def run(self, algorithm):
        """Monitor and enforce risk limits"""
        
        # Check portfolio drawdown
        self.check_drawdown(algorithm)
        
        # Check position sizes
        self.check_position_sizes(algorithm)
        
        # Check correlation exposure
        self.check_correlation_risk(algorithm)
    
    def check_drawdown(self, algorithm):
        """Check if portfolio drawdown exceeds limit"""
        
        portfolio = algorithm.get_portfolio()
        peak_value = portfolio.get_peak_value()
        current_value = portfolio.get_total_value()
        
        drawdown = (peak_value - current_value) / peak_value
        
        if drawdown > self.max_drawdown:
            # Emergency risk reduction
            self.reduce_risk(algorithm, f"Drawdown {drawdown:.2%} exceeds limit")
    
    def check_position_sizes(self, algorithm):
        """Check if any position is too large"""
        
        portfolio = algorithm.get_portfolio()
        positions = algorithm.get_positions()
        total_value = portfolio.get_total_value()
        
        for position in positions:
            position_weight = position.current_value / total_value
            
            if position_weight > self.max_position_size:
                # Reduce oversized position
                target_symbol = position.symbol.split('/')[0]
                excess_percentage = position_weight - self.max_position_size
                
                algorithm.create_sell_order(
                    target_symbol=target_symbol,
                    percentage=excess_percentage / position_weight,
                    order_type="MARKET"
                )
                
                print(f"Reduced oversized position: {position.symbol}")
    
    def reduce_risk(self, algorithm, reason):
        """Emergency risk reduction"""
        
        print(f"RISK ALERT: {reason}")
        print("Implementing risk reduction measures...")
        
        # Cancel all open orders
        algorithm.cancel_all_orders()
        
        # Reduce position sizes by 50%
        positions = algorithm.get_positions()
        for position in positions:
            target_symbol = position.symbol.split('/')[0]
            algorithm.create_sell_order(
                target_symbol=target_symbol,
                percentage=0.5,
                order_type="MARKET"
            )
        
        print("Risk reduction completed")
```

### Database Maintenance

```python
class DatabaseMaintenanceTask(Task):
    
    def __init__(self):
        super().__init__(
            name="database_maintenance",
            interval="daily",
            time="03:00"  # 3 AM daily
        )
    
    def run(self, algorithm):
        """Perform database maintenance tasks"""
        
        print("Starting database maintenance...")
        
        # Archive old data
        self.archive_old_data(algorithm)
        
        # Optimize database
        self.optimize_database(algorithm)
        
        # Backup database
        self.backup_database(algorithm)
        
        print("Database maintenance completed")
    
    def archive_old_data(self, algorithm):
        """Archive old market data and trades"""
        
        cutoff_date = datetime.now() - timedelta(days=365)
        
        # Archive old trades
        old_trades = algorithm.get_trades(before_date=cutoff_date)
        if old_trades:
            algorithm.archive_trades(old_trades)
            print(f"Archived {len(old_trades)} old trades")
        
        # Archive old market data
        algorithm.archive_market_data(before_date=cutoff_date)
    
    def optimize_database(self, algorithm):
        """Optimize database performance"""
        
        # Rebuild indices
        algorithm.rebuild_database_indices()
        
        # Update statistics
        algorithm.update_database_statistics()
        
        print("Database optimization completed")
    
    def backup_database(self, algorithm):
        """Create database backup"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"/backups/trading_db_backup_{timestamp}.sql"
        
        algorithm.backup_database(backup_path)
        print(f"Database backed up to {backup_path}")
```

## Task Management

### Task Monitoring

```python
class TaskMonitor(Task):
    
    def __init__(self):
        super().__init__(
            name="task_monitor",
            interval="10m"
        )
        self.task_history = {}
    
    def run(self, algorithm):
        """Monitor other tasks for failures"""
        
        # Get task execution history
        task_status = algorithm.get_task_status()
        
        for task_name, status in task_status.items():
            if status.get('last_error'):
                print(f"Task {task_name} failed: {status['last_error']}")
            
            # Check if task is overdue
            last_run = status.get('last_run')
            if last_run:
                time_since_run = datetime.now() - last_run
                if time_since_run > timedelta(hours=2):  # Configurable threshold
                    print(f"Task {task_name} is overdue (last run: {last_run})")
```

### Conditional Tasks

```python
class ConditionalRebalanceTask(Task):
    
    def __init__(self):
        super().__init__(
            name="conditional_rebalance",
            interval="1h"
        )
    
    def run(self, algorithm):
        """Only rebalance if conditions are met"""
        
        # Check if rebalancing is needed
        if not self.should_rebalance(algorithm):
            return
        
        print("Rebalancing conditions met - executing rebalance")
        self.execute_rebalance(algorithm)
    
    def should_rebalance(self, algorithm):
        """Check if rebalancing conditions are met"""
        
        positions = algorithm.get_positions()
        portfolio = algorithm.get_portfolio()
        total_value = portfolio.get_total_value()
        
        # Check if any position deviates more than 5% from target
        target_weights = {"BTC": 0.5, "ETH": 0.3, "ADA": 0.2}
        
        for symbol, target_weight in target_weights.items():
            position = next(
                (p for p in positions if p.symbol.startswith(symbol)), 
                None
            )
            
            current_weight = (position.current_value / total_value) if position else 0
            
            if abs(current_weight - target_weight) > 0.05:
                return True
        
        return False
    
    def execute_rebalance(self, algorithm):
        """Execute portfolio rebalancing"""
        # Implementation for rebalancing logic
        pass
```

## Best Practices

### 1. Error Handling

```python
class RobustTask(Task):
    
    def __init__(self):
        super().__init__(name="robust_task", interval="5m")
        self.max_retries = 3
        self.retry_delay = 30  # seconds
    
    def run(self, algorithm):
        """Run task with error handling and retries"""
        
        for attempt in range(self.max_retries):
            try:
                self.execute_task_logic(algorithm)
                return  # Success, exit retry loop
                
            except Exception as e:
                print(f"Task attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    print(f"Task failed after {self.max_retries} attempts")
                    self.handle_task_failure(e)
    
    def execute_task_logic(self, algorithm):
        """Main task logic that might fail"""
        # Implementation here
        pass
    
    def handle_task_failure(self, error):
        """Handle permanent task failure"""
        # Log error, send alerts, etc.
        pass
```

### 2. Resource Management

```python
class ResourceAwareTask(Task):
    
    def run(self, algorithm):
        """Task that monitors resource usage"""
        
        # Check system resources before running
        if not self.has_sufficient_resources():
            print("Insufficient resources - skipping task execution")
            return
        
        # Execute task logic
        self.execute_heavy_computation()
    
    def has_sufficient_resources(self):
        """Check if system has sufficient resources"""
        import psutil
        
        # Check memory usage
        memory_percent = psutil.virtual_memory().percent
        if memory_percent > 90:
            return False
        
        # Check CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 95:
            return False
        
        return True
```

### 3. Task Dependencies

```python
class DependentTask(Task):
    
    def __init__(self, prerequisite_tasks):
        super().__init__(name="dependent_task", interval="1h")
        self.prerequisite_tasks = prerequisite_tasks
    
    def run(self, algorithm):
        """Only run if prerequisite tasks completed successfully"""
        
        # Check if prerequisites are met
        if not self.prerequisites_met(algorithm):
            print("Prerequisites not met - skipping task")
            return
        
        # Execute task logic
        self.execute_task(algorithm)
    
    def prerequisites_met(self, algorithm):
        """Check if prerequisite tasks completed successfully"""
        
        task_status = algorithm.get_task_status()
        
        for prereq_task in self.prerequisite_tasks:
            status = task_status.get(prereq_task, {})
            
            if status.get('last_error'):
                return False
            
            # Check if task ran recently
            last_run = status.get('last_run')
            if not last_run or (datetime.now() - last_run) > timedelta(hours=2):
                return False
        
        return True
```

## Next Steps

Tasks provide powerful automation capabilities for your trading system. Next, learn about [Backtesting](backtesting) to test your strategies and tasks against historical data before deploying them live.
