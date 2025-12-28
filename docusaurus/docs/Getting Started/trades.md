---
sidebar_position: 7
---

# Trades

Understand how individual trades work and how to track trading performance.

## Overview

Trades represent completed transactions in your trading system. Unlike orders (which are instructions to trade) or positions (which represent holdings), trades are the actual executed transactions that move money between your cash balance and asset holdings.

## Understanding Trades

### Trade Lifecycle

1. **Order Placed**: You create a buy or sell order
2. **Order Executed**: The market fills your order
3. **Trade Created**: A trade record is generated
4. **Position Updated**: Your asset holdings are adjusted
5. **Portfolio Updated**: Your portfolio balance reflects the trade

### Trade Properties

```python
def analyze_trade(self, trade):
    """Analyze a completed trade"""
    
    print(f"Trade ID: {trade.id}")
    print(f"Symbol: {trade.target_symbol}/{trade.trading_symbol}")
    print(f"Side: {trade.side}")  # BUY or SELL
    print(f"Amount: {trade.amount}")
    print(f"Price: ${trade.price:.2f}")
    print(f"Total Cost: ${trade.cost:.2f}")
    print(f"Fee: ${trade.fee:.2f}")
    print(f"Timestamp: {trade.created_at}")
    print(f"Status: {trade.status}")
```

## Accessing Trade Data

### Get All Trades

```python
def review_trading_history(self, algorithm):
    """Review all completed trades"""
    trades = algorithm.get_trades()
    
    total_trades = len(trades)
    total_volume = sum(trade.cost for trade in trades)
    total_fees = sum(trade.fee for trade in trades)
    
    print(f"Total Trades: {total_trades}")
    print(f"Total Volume: ${total_volume:.2f}")
    print(f"Total Fees: ${total_fees:.2f}")
    
    return trades
```

### Filter Trades

```python
def filter_trades(self, algorithm, symbol=None, days=None):
    """Filter trades by symbol and time period"""
    trades = algorithm.get_trades()
    
    # Filter by symbol
    if symbol:
        trades = [t for t in trades if t.target_symbol == symbol]
    
    # Filter by date range
    if days:
        cutoff_date = datetime.now() - timedelta(days=days)
        trades = [t for t in trades if t.created_at >= cutoff_date]
    
    return trades

# Examples
recent_btc_trades = self.filter_trades(algorithm, symbol="BTC", days=7)
all_recent_trades = self.filter_trades(algorithm, days=30)
```

### Trade Statistics

```python
def calculate_trade_statistics(self, trades):
    """Calculate trading performance statistics"""
    
    if not trades:
        return {"error": "No trades found"}
    
    buy_trades = [t for t in trades if t.side == "BUY"]
    sell_trades = [t for t in trades if t.side == "SELL"]
    
    stats = {
        "total_trades": len(trades),
        "buy_trades": len(buy_trades),
        "sell_trades": len(sell_trades),
        "total_volume": sum(t.cost for t in trades),
        "total_fees": sum(t.fee for t in trades),
        "average_trade_size": sum(t.cost for t in trades) / len(trades),
        "largest_trade": max(t.cost for t in trades),
        "smallest_trade": min(t.cost for t in trades),
    }
    
    return stats
```

## Trade Performance Analysis

### Profit and Loss Tracking

```python
class TradeAnalyzer:
    def __init__(self, algorithm):
        self.algorithm = algorithm
    
    def match_buy_sell_trades(self, symbol):
        """Match buy and sell trades to calculate P&L"""
        trades = self.algorithm.get_trades()
        symbol_trades = [t for t in trades if t.target_symbol == symbol]
        
        # Separate buy and sell trades
        buys = [t for t in symbol_trades if t.side == "BUY"]
        sells = [t for t in symbol_trades if t.side == "SELL"]
        
        # Sort by timestamp
        buys.sort(key=lambda x: x.created_at)
        sells.sort(key=lambda x: x.created_at)
        
        return self._calculate_fifo_pnl(buys, sells)
    
    def _calculate_fifo_pnl(self, buys, sells):
        """Calculate P&L using FIFO method"""
        realized_pnl = 0
        buy_queue = [(trade.amount, trade.price) for trade in buys]
        
        for sell_trade in sells:
            sell_amount = sell_trade.amount
            sell_price = sell_trade.price
            
            while sell_amount > 0 and buy_queue:
                buy_amount, buy_price = buy_queue[0]
                
                # Calculate trade quantity
                trade_qty = min(sell_amount, buy_amount)
                
                # Calculate P&L for this portion
                pnl = trade_qty * (sell_price - buy_price)
                realized_pnl += pnl
                
                # Update amounts
                sell_amount -= trade_qty
                buy_queue[0] = (buy_amount - trade_qty, buy_price)
                
                # Remove empty buy order
                if buy_queue[0][0] == 0:
                    buy_queue.pop(0)
        
        return realized_pnl
```

### Win Rate Analysis

```python
def calculate_win_rate(self, algorithm, symbol):
    """Calculate win rate for a specific symbol"""
    analyzer = TradeAnalyzer(algorithm)
    
    # Get all completed round trips (buy-sell pairs)
    round_trips = analyzer.get_round_trip_trades(symbol)
    
    if not round_trips:
        return {"error": "No completed round trips found"}
    
    winning_trades = [rt for rt in round_trips if rt['pnl'] > 0]
    losing_trades = [rt for rt in round_trips if rt['pnl'] < 0]
    
    win_rate = len(winning_trades) / len(round_trips) * 100
    
    avg_win = sum(rt['pnl'] for rt in winning_trades) / len(winning_trades) if winning_trades else 0
    avg_loss = sum(rt['pnl'] for rt in losing_trades) / len(losing_trades) if losing_trades else 0
    
    return {
        "total_round_trips": len(round_trips),
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": win_rate,
        "average_win": avg_win,
        "average_loss": avg_loss,
        "profit_factor": abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
    }
```

## Trade Monitoring

### Real-time Trade Tracking

```python
class TradeMonitor:
    def __init__(self):
        self.last_trade_count = 0
    
    def check_new_trades(self, algorithm):
        """Check for new trades and log them"""
        current_trades = algorithm.get_trades()
        current_count = len(current_trades)
        
        if current_count > self.last_trade_count:
            # New trades detected
            new_trades = current_trades[self.last_trade_count:]
            
            for trade in new_trades:
                self.log_new_trade(trade)
            
            self.last_trade_count = current_count
    
    def log_new_trade(self, trade):
        """Log details of a new trade"""
        side_emoji = "🟢" if trade.side == "BUY" else "🔴"
        
        print(f"{side_emoji} NEW TRADE:")
        print(f"   Symbol: {trade.target_symbol}")
        print(f"   Side: {trade.side}")
        print(f"   Amount: {trade.amount}")
        print(f"   Price: ${trade.price:.2f}")
        print(f"   Total: ${trade.cost:.2f}")
        print(f"   Fee: ${trade.fee:.2f}")
        print(f"   Time: {trade.created_at}")
        print("-" * 40)
```

### Trade Alerts

```python
class TradeAlertSystem:
    def __init__(self, alert_manager):
        self.alert_manager = alert_manager
        self.thresholds = {
            "large_trade_amount": 1000,  # Alert for trades > $1000
            "high_fee_percentage": 0.005,  # Alert for fees > 0.5%
            "rapid_trading": 5  # Alert if more than 5 trades in 1 minute
        }
    
    def check_trade_alerts(self, trade):
        """Check if trade triggers any alerts"""
        
        # Large trade alert
        if trade.cost > self.thresholds["large_trade_amount"]:
            self.alert_manager.send_alert(
                f"Large trade executed: {trade.target_symbol} "
                f"${trade.cost:.2f}",
                severity="INFO"
            )
        
        # High fee alert
        fee_percentage = trade.fee / trade.cost if trade.cost > 0 else 0
        if fee_percentage > self.thresholds["high_fee_percentage"]:
            self.alert_manager.send_alert(
                f"High fee trade: {trade.target_symbol} "
                f"fee {fee_percentage:.3%}",
                severity="WARNING"
            )
```

## Trade Reporting

### Daily Trading Summary

```python
def generate_daily_summary(self, algorithm, date=None):
    """Generate daily trading summary"""
    
    if date is None:
        date = datetime.now().date()
    
    # Get trades for the day
    start_of_day = datetime.combine(date, datetime.min.time())
    end_of_day = datetime.combine(date, datetime.max.time())
    
    daily_trades = [
        t for t in algorithm.get_trades()
        if start_of_day <= t.created_at <= end_of_day
    ]
    
    if not daily_trades:
        return f"No trades on {date}"
    
    # Calculate summary statistics
    total_volume = sum(t.cost for t in daily_trades)
    total_fees = sum(t.fee for t in daily_trades)
    unique_symbols = set(t.target_symbol for t in daily_trades)
    
    summary = f"""
    Daily Trading Summary - {date}
    {'='*40}
    Total Trades: {len(daily_trades)}
    Total Volume: ${total_volume:.2f}
    Total Fees: ${total_fees:.2f}
    Symbols Traded: {', '.join(unique_symbols)}
    Average Trade Size: ${total_volume/len(daily_trades):.2f}
    Fee Rate: {(total_fees/total_volume)*100:.3f}%
    """
    
    return summary
```

### Trade Export

```python
import pandas as pd

def export_trades_to_csv(self, algorithm, filename="trades.csv"):
    """Export trades to CSV file"""
    trades = algorithm.get_trades()
    
    # Convert to pandas DataFrame
    trade_data = []
    for trade in trades:
        trade_data.append({
            'id': trade.id,
            'timestamp': trade.created_at,
            'symbol': f"{trade.target_symbol}/{trade.trading_symbol}",
            'side': trade.side,
            'amount': trade.amount,
            'price': trade.price,
            'cost': trade.cost,
            'fee': trade.fee,
            'status': trade.status
        })
    
    df = pd.DataFrame(trade_data)
    df.to_csv(filename, index=False)
    
    print(f"Exported {len(trades)} trades to {filename}")
    return df
```

## Advanced Trade Analysis

### Trade Timing Analysis

```python
def analyze_trade_timing(self, algorithm, symbol):
    """Analyze timing patterns in trades"""
    trades = [t for t in algorithm.get_trades() if t.target_symbol == symbol]
    
    if len(trades) < 2:
        return "Insufficient data for timing analysis"
    
    # Calculate time between trades
    trade_intervals = []
    for i in range(1, len(trades)):
        interval = trades[i].created_at - trades[i-1].created_at
        trade_intervals.append(interval.total_seconds())
    
    avg_interval = sum(trade_intervals) / len(trade_intervals)
    min_interval = min(trade_intervals)
    max_interval = max(trade_intervals)
    
    return {
        "average_interval_seconds": avg_interval,
        "min_interval_seconds": min_interval,
        "max_interval_seconds": max_interval,
        "total_trades": len(trades),
        "trading_period_days": (trades[-1].created_at - trades[0].created_at).days
    }
```

### Trade Size Distribution

```python
import matplotlib.pyplot as plt

def plot_trade_size_distribution(self, algorithm):
    """Plot distribution of trade sizes"""
    trades = algorithm.get_trades()
    trade_sizes = [t.cost for t in trades]
    
    plt.figure(figsize=(10, 6))
    plt.hist(trade_sizes, bins=20, edgecolor='black', alpha=0.7)
    plt.title('Trade Size Distribution')
    plt.xlabel('Trade Size ($)')
    plt.ylabel('Frequency')
    plt.grid(True, alpha=0.3)
    
    # Add statistics
    avg_size = sum(trade_sizes) / len(trade_sizes)
    plt.axvline(avg_size, color='red', linestyle='--', 
                label=f'Average: ${avg_size:.2f}')
    plt.legend()
    
    plt.tight_layout()
    plt.show()
```

## Best Practices

### 1. Trade Validation

```python
def validate_trade_execution(self, expected_trade, actual_trade):
    """Validate that trade executed as expected"""
    
    tolerance = 0.01  # 1% tolerance for price differences
    
    checks = {
        "symbol_match": expected_trade.symbol == actual_trade.target_symbol,
        "side_match": expected_trade.side == actual_trade.side,
        "amount_match": abs(expected_trade.amount - actual_trade.amount) < 0.001,
        "price_reasonable": abs(expected_trade.price - actual_trade.price) / expected_trade.price < tolerance
    }
    
    if not all(checks.values()):
        print(f"Trade validation failed: {checks}")
        return False
    
    return True
```

### 2. Trade Reconciliation

```python
def reconcile_trades_with_exchange(self, algorithm, exchange):
    """Reconcile internal trades with exchange records"""
    
    internal_trades = algorithm.get_trades()
    exchange_trades = exchange.fetch_my_trades()
    
    # Compare trade counts and totals
    internal_count = len(internal_trades)
    exchange_count = len(exchange_trades)
    
    if internal_count != exchange_count:
        print(f"Trade count mismatch: Internal={internal_count}, Exchange={exchange_count}")
    
    # Compare total volumes
    internal_volume = sum(t.cost for t in internal_trades)
    exchange_volume = sum(t['cost'] for t in exchange_trades)
    
    if abs(internal_volume - exchange_volume) > 1.0:  # $1 tolerance
        print(f"Volume mismatch: Internal=${internal_volume:.2f}, Exchange=${exchange_volume:.2f}")
```

### 3. Trade History Maintenance

```python
def archive_old_trades(self, algorithm, days_to_keep=365):
    """Archive trades older than specified days"""
    
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    all_trades = algorithm.get_trades()
    
    old_trades = [t for t in all_trades if t.created_at < cutoff_date]
    recent_trades = [t for t in all_trades if t.created_at >= cutoff_date]
    
    if old_trades:
        # Export old trades before archiving
        self.export_trades_to_csv(
            old_trades, 
            f"archived_trades_{cutoff_date.strftime('%Y%m%d')}.csv"
        )
        
        # Remove from active database (implementation specific)
        algorithm.archive_trades(old_trades)
        
        print(f"Archived {len(old_trades)} old trades")
```

## Next Steps

Understanding trades is crucial for performance analysis and strategy optimization. Next, learn about [Tasks](tasks) to automate trade analysis and reporting processes.
