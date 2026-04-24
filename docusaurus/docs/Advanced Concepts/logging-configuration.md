---
sidebar_position: 1
---

# Logging Configuration

Learn how to configure comprehensive logging for your trading algorithms to monitor performance, debug issues, and maintain audit trails.

## Overview

Proper logging is essential for production trading systems. It enables monitoring, debugging, compliance tracking, and performance analysis. The framework provides flexible logging configuration options that can be customized for different environments and requirements.

## Basic Logging Setup

### Default Logging

```python
import logging
from investing_algorithm_framework import create_app

# Create app with default logging
app = create_app()

# The framework automatically sets up basic logging
# Logs will be written to console and file
```

### Simple Custom Configuration

```python
import logging

# Configure logging before creating the app
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('trading_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('trading_bot')
logger.info("Trading bot starting...")

app = create_app()
```

## Advanced Logging Configuration

### Structured Logging Configuration

```python
import logging
import logging.config
import os
from datetime import datetime

# Define logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        },
        'simple': {
            'format': '%(asctime)s - %(levelname)s - %(message)s'
        },
        'json': {
            'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(funcName)s %(lineno)d %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'stream': 'ext://sys.stdout'
        },
        'file_handler': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filename': 'logs/trading_bot.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'encoding': 'utf8'
        },
        'error_file_handler': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'ERROR',
            'formatter': 'detailed', 
            'filename': 'logs/errors.log',
            'maxBytes': 10485760,
            'backupCount': 5,
            'encoding': 'utf8'
        },
        'trade_file_handler': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'json',
            'filename': 'logs/trades.log',
            'maxBytes': 10485760,
            'backupCount': 10,
            'encoding': 'utf8'
        }
    },
    'loggers': {
        '': {  # Root logger
            'level': 'INFO',
            'handlers': ['console', 'file_handler', 'error_file_handler']
        },
        'trading_bot': {
            'level': 'DEBUG',
            'handlers': ['console', 'file_handler'],
            'propagate': False
        },
        'trading_bot.trades': {
            'level': 'INFO',
            'handlers': ['trade_file_handler'],
            'propagate': False
        },
        'trading_bot.strategy': {
            'level': 'DEBUG',
            'handlers': ['console', 'file_handler'],
            'propagate': False
        }
    }
}

# Apply logging configuration
os.makedirs('logs', exist_ok=True)
logging.config.dictConfig(LOGGING_CONFIG)

# Create specialized loggers
main_logger = logging.getLogger('trading_bot')
trade_logger = logging.getLogger('trading_bot.trades')
strategy_logger = logging.getLogger('trading_bot.strategy')
```

### Environment-Based Configuration

```python
import os

def get_logging_config():
    """Get logging configuration based on environment"""
    
    environment = os.getenv('ENVIRONMENT', 'development')
    
    if environment == 'production':
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'production': {
                    'class': 'pythonjsonlogger.jsonlogger.JsonFormatter',
                    'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
                }
            },
            'handlers': {
                'file': {
                    'class': 'logging.handlers.RotatingFileHandler',
                    'level': 'INFO',
                    'formatter': 'production',
                    'filename': '/var/log/trading-bot/app.log',
                    'maxBytes': 50485760,  # 50MB
                    'backupCount': 10
                },
                'syslog': {
                    'class': 'logging.handlers.SysLogHandler',
                    'level': 'WARNING',
                    'formatter': 'production',
                    'address': ('localhost', 514)
                }
            },
            'loggers': {
                '': {
                    'level': 'INFO',
                    'handlers': ['file', 'syslog']
                }
            }
        }
    
    elif environment == 'development':
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'development': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'level': 'DEBUG',
                    'formatter': 'development'
                },
                'file': {
                    'class': 'logging.FileHandler',
                    'level': 'DEBUG',
                    'formatter': 'development',
                    'filename': 'development.log'
                }
            },
            'loggers': {
                '': {
                    'level': 'DEBUG',
                    'handlers': ['console', 'file']
                }
            }
        }
    
    else:  # testing
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'handlers': {
                'null': {
                    'class': 'logging.NullHandler'
                }
            },
            'loggers': {
                '': {
                    'level': 'CRITICAL',
                    'handlers': ['null']
                }
            }
        }

# Configure logging based on environment
logging.config.dictConfig(get_logging_config())
```

## Specialized Loggers

### Strategy Logging

```python
import logging

class LoggedStrategy(TradingStrategy):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger('trading_bot.strategy')
        
    def apply_strategy(self, algorithm, market_data):
        self.logger.info("Strategy execution started")
        
        try:
            symbol = "BTC/USDT"
            current_price = market_data.get_last_price(symbol)
            
            self.logger.debug(f"Current {symbol} price: ${current_price:.2f}")
            
            # Strategy logic
            if self.should_buy(current_price):
                self.logger.info(f"Buy signal generated for {symbol} at ${current_price:.2f}")
                
                order = algorithm.create_buy_order(
                    target_symbol="BTC",
                    amount=100,
                    order_type="MARKET"
                )
                
                self.logger.info(f"Buy order created: {order.id}")
                
            elif self.should_sell(current_price):
                self.logger.info(f"Sell signal generated for {symbol} at ${current_price:.2f}")
                
                order = algorithm.create_sell_order(
                    target_symbol="BTC",
                    percentage=1.0,
                    order_type="MARKET"
                )
                
                self.logger.info(f"Sell order created: {order.id}")
            
            else:
                self.logger.debug(f"No action taken for {symbol}")
                
        except Exception as e:
            self.logger.error(f"Strategy execution failed: {e}", exc_info=True)
            raise
        
        finally:
            self.logger.info("Strategy execution completed")
    
    def should_buy(self, price):
        # Buy logic with logging
        self.logger.debug(f"Evaluating buy conditions at price ${price:.2f}")
        return False
        
    def should_sell(self, price):
        # Sell logic with logging
        self.logger.debug(f"Evaluating sell conditions at price ${price:.2f}")
        return False
```

### Trade Logging

```python
class TradeLogger:
    def __init__(self):
        self.logger = logging.getLogger('trading_bot.trades')
    
    def log_order_created(self, order):
        """Log order creation"""
        self.logger.info("Order created", extra={
            'event_type': 'order_created',
            'order_id': order.id,
            'symbol': f"{order.target_symbol}/{order.trading_symbol}",
            'side': order.order_side,
            'type': order.order_type,
            'amount': order.amount,
            'price': order.price,
            'status': order.status,
            'timestamp': order.created_at.isoformat()
        })
    
    def log_order_filled(self, order):
        """Log order execution"""
        self.logger.info("Order filled", extra={
            'event_type': 'order_filled',
            'order_id': order.id,
            'symbol': f"{order.target_symbol}/{order.trading_symbol}",
            'side': order.order_side,
            'amount': order.amount,
            'price': order.price,
            'cost': order.cost,
            'fee': order.fee if hasattr(order, 'fee') else 0,
            'status': order.status,
            'filled_at': order.updated_at.isoformat()
        })
    
    def log_position_opened(self, position):
        """Log position opening"""
        self.logger.info("Position opened", extra={
            'event_type': 'position_opened',
            'symbol': position.symbol,
            'amount': position.amount,
            'entry_price': position.entry_price,
            'timestamp': position.opened_at.isoformat()
        })
    
    def log_position_closed(self, position, exit_price, pnl):
        """Log position closing"""
        self.logger.info("Position closed", extra={
            'event_type': 'position_closed',
            'symbol': position.symbol,
            'amount': position.amount,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'pnl': pnl,
            'pnl_percentage': (pnl / (position.amount * position.entry_price)) * 100,
            'timestamp': datetime.now().isoformat()
        })

# Integrate trade logging with strategy
class LoggedTradingStrategy(TradingStrategy):
    def __init__(self):
        super().__init__()
        self.trade_logger = TradeLogger()
        
    def apply_strategy(self, algorithm, market_data):
        # Strategy logic...
        
        # Log trades when they occur
        orders = algorithm.get_orders()
        for order in orders:
            if order.status == "FILLED" and not hasattr(order, '_logged'):
                self.trade_logger.log_order_filled(order)
                order._logged = True
```

### Performance Logging

```python
import time
import psutil
from functools import wraps

class PerformanceLogger:
    def __init__(self):
        self.logger = logging.getLogger('trading_bot.performance')
    
    def log_execution_time(self, func):
        """Decorator to log function execution time"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                self.logger.info("Function executed", extra={
                    'function': func.__name__,
                    'execution_time': execution_time,
                    'status': 'success'
                })
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                
                self.logger.error("Function failed", extra={
                    'function': func.__name__,
                    'execution_time': execution_time,
                    'status': 'error',
                    'error': str(e)
                })
                raise
        
        return wrapper
    
    def log_system_metrics(self):
        """Log system performance metrics"""
        cpu_percent = psutil.cpu_percent()
        memory_info = psutil.virtual_memory()
        
        self.logger.info("System metrics", extra={
            'cpu_percent': cpu_percent,
            'memory_percent': memory_info.percent,
            'memory_available': memory_info.available,
            'memory_used': memory_info.used
        })

# Use performance logging
perf_logger = PerformanceLogger()

class PerformanceMonitoredStrategy(TradingStrategy):
    
    @perf_logger.log_execution_time
    def apply_strategy(self, algorithm, market_data):
        # Strategy logic...
        pass
    
    @perf_logger.log_execution_time
    def analyze_market_data(self, market_data):
        # Analysis logic...
        pass
```

## Log Analysis and Monitoring

### Log Parsing

```python
import json
from datetime import datetime

class LogAnalyzer:
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
    
    def parse_trade_logs(self, start_date=None, end_date=None):
        """Parse trade logs and extract trading activity"""
        
        trades = []
        
        with open(self.log_file_path, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    
                    # Filter by date range if specified
                    if start_date or end_date:
                        log_time = datetime.fromisoformat(log_entry['asctime'])
                        if start_date and log_time < start_date:
                            continue
                        if end_date and log_time > end_date:
                            continue
                    
                    # Extract trade events
                    if log_entry.get('event_type') in ['order_created', 'order_filled']:
                        trades.append(log_entry)
                        
                except (json.JSONDecodeError, KeyError):
                    # Skip malformed log entries
                    continue
        
        return trades
    
    def calculate_trading_stats(self, trades):
        """Calculate trading statistics from logs"""
        
        stats = {
            'total_orders': len(trades),
            'buy_orders': len([t for t in trades if t.get('side') == 'BUY']),
            'sell_orders': len([t for t in trades if t.get('side') == 'SELL']),
            'filled_orders': len([t for t in trades if t.get('event_type') == 'order_filled']),
            'total_volume': sum(t.get('cost', 0) for t in trades if t.get('event_type') == 'order_filled'),
            'symbols_traded': list(set(t.get('symbol') for t in trades if t.get('symbol')))
        }
        
        return stats
    
    def detect_errors(self, start_date=None, end_date=None):
        """Detect and analyze errors from logs"""
        
        errors = []
        
        with open(self.log_file_path, 'r') as f:
            for line in f:
                try:
                    log_entry = json.loads(line.strip())
                    
                    if log_entry.get('levelname') in ['ERROR', 'CRITICAL']:
                        # Filter by date if specified
                        if start_date or end_date:
                            log_time = datetime.fromisoformat(log_entry['asctime'])
                            if start_date and log_time < start_date:
                                continue
                            if end_date and log_time > end_date:
                                continue
                        
                        errors.append(log_entry)
                        
                except (json.JSONDecodeError, KeyError):
                    continue
        
        return errors

# Analyze logs
analyzer = LogAnalyzer('logs/trades.log')
trades = analyzer.parse_trade_logs(start_date=datetime(2024, 1, 1))
stats = analyzer.calculate_trading_stats(trades)

print(f"Trading Statistics:")
print(f"Total Orders: {stats['total_orders']}")
print(f"Buy Orders: {stats['buy_orders']}")
print(f"Sell Orders: {stats['sell_orders']}")
print(f"Total Volume: ${stats['total_volume']:.2f}")
```

### Real-time Log Monitoring

```python
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class LogMonitor(FileSystemEventHandler):
    def __init__(self, log_file_path, alert_callback=None):
        self.log_file_path = log_file_path
        self.alert_callback = alert_callback
        self.file_position = 0
        
        # Get initial file size
        try:
            with open(log_file_path, 'r') as f:
                f.seek(0, 2)  # Seek to end
                self.file_position = f.tell()
        except FileNotFoundError:
            self.file_position = 0
    
    def on_modified(self, event):
        if event.src_path == self.log_file_path:
            self.process_new_log_entries()
    
    def process_new_log_entries(self):
        """Process new log entries"""
        try:
            with open(self.log_file_path, 'r') as f:
                f.seek(self.file_position)
                new_lines = f.readlines()
                self.file_position = f.tell()
                
                for line in new_lines:
                    self.analyze_log_entry(line.strip())
                    
        except Exception as e:
            print(f"Error processing log entries: {e}")
    
    def analyze_log_entry(self, line):
        """Analyze individual log entry"""
        try:
            log_entry = json.loads(line)
            
            # Check for critical errors
            if log_entry.get('levelname') == 'CRITICAL':
                self.handle_critical_error(log_entry)
            
            # Check for trading anomalies
            elif log_entry.get('event_type') == 'order_filled':
                self.check_trading_anomalies(log_entry)
                
        except json.JSONDecodeError:
            # Skip non-JSON log entries
            pass
    
    def handle_critical_error(self, log_entry):
        """Handle critical errors"""
        if self.alert_callback:
            self.alert_callback(f"CRITICAL ERROR: {log_entry.get('message')}")
    
    def check_trading_anomalies(self, log_entry):
        """Check for trading anomalies"""
        # Example: Alert on large trades
        cost = log_entry.get('cost', 0)
        if cost > 10000:  # $10k+ trade
            if self.alert_callback:
                self.alert_callback(f"Large trade detected: ${cost:.2f}")

def send_alert(message):
    """Send alert notification"""
    print(f"🚨 ALERT: {message}")
    # Could send email, Slack notification, etc.

# Setup log monitoring
monitor = LogMonitor('logs/app.log', alert_callback=send_alert)

observer = Observer()
observer.schedule(monitor, path='logs', recursive=False)
observer.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()
```

## Production Logging Best Practices

### Security and Compliance

```python
import hashlib

class SecureLogger:
    def __init__(self, logger):
        self.logger = logger
    
    def log_sensitive_data(self, message, sensitive_fields=None):
        """Log with sensitive data masking"""
        
        if sensitive_fields:
            for field in sensitive_fields:
                if field in message:
                    # Mask sensitive data
                    original_value = message[field]
                    if isinstance(original_value, str):
                        masked_value = self.mask_string(original_value)
                    else:
                        masked_value = "***MASKED***"
                    message[field] = masked_value
        
        self.logger.info(message)
    
    def mask_string(self, value, show_chars=4):
        """Mask string value keeping only first/last characters"""
        if len(value) <= show_chars * 2:
            return "*" * len(value)
        
        return value[:show_chars] + "*" * (len(value) - show_chars * 2) + value[-show_chars:]
    
    def log_api_call(self, endpoint, api_key):
        """Log API call with masked credentials"""
        self.logger.info("API call made", extra={
            'endpoint': endpoint,
            'api_key_hash': hashlib.sha256(api_key.encode()).hexdigest()[:16],
            'timestamp': datetime.now().isoformat()
        })

# Use secure logging
secure_logger = SecureLogger(logging.getLogger('trading_bot.secure'))

# Log sensitive data safely
user_data = {
    'user_id': '12345',
    'email': 'user@example.com',
    'api_key': 'secret_api_key_12345',
    'balance': 10000.0
}

secure_logger.log_sensitive_data(
    user_data.copy(),
    sensitive_fields=['email', 'api_key']
)
```

### Log Retention and Archival

```python
import gzip
import shutil
from pathlib import Path

class LogArchiver:
    def __init__(self, log_directory, retention_days=90):
        self.log_directory = Path(log_directory)
        self.retention_days = retention_days
    
    def archive_old_logs(self):
        """Archive old log files"""
        
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        
        for log_file in self.log_directory.glob('*.log*'):
            if log_file.stat().st_mtime < cutoff_date.timestamp():
                
                # Compress old logs
                if not log_file.name.endswith('.gz'):
                    self.compress_log(log_file)
                
                # Move to archive directory
                archive_dir = self.log_directory / 'archive'
                archive_dir.mkdir(exist_ok=True)
                
                archive_path = archive_dir / log_file.name
                shutil.move(str(log_file), str(archive_path))
                
                print(f"Archived log file: {log_file.name}")
    
    def compress_log(self, log_file):
        """Compress log file"""
        compressed_file = log_file.with_suffix(log_file.suffix + '.gz')
        
        with open(log_file, 'rb') as f_in:
            with gzip.open(compressed_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        log_file.unlink()  # Remove original file
        return compressed_file

# Schedule log archival
archiver = LogArchiver('logs', retention_days=30)
archiver.archive_old_logs()
```

## Integration with Framework

### App-Level Logging

```python
from investing_algorithm_framework import create_app

# Configure logging before creating app
logging.config.dictConfig(LOGGING_CONFIG)

app = create_app()

# Add logging to app lifecycle events
@app.on_startup
def log_startup():
    logger = logging.getLogger('trading_bot')
    logger.info("Trading application started", extra={
        'event': 'app_startup',
        'timestamp': datetime.now().isoformat()
    })

@app.on_shutdown  
def log_shutdown():
    logger = logging.getLogger('trading_bot')
    logger.info("Trading application stopped", extra={
        'event': 'app_shutdown', 
        'timestamp': datetime.now().isoformat()
    })

# Add strategy with logging
logged_strategy = LoggedStrategy()
app.add_strategy(logged_strategy)

# Start app with logging
app.start_trading()
```

## Next Steps

Proper logging configuration enables:

1. **Production Monitoring**: Track system health and performance
2. **Debugging**: Quickly identify and resolve issues
3. **Compliance**: Maintain audit trails for regulatory requirements
4. **Analytics**: Analyze trading performance and system behavior

Combine logging with monitoring tools like Grafana, ELK stack, or cloud logging services for comprehensive observability in production environments.
