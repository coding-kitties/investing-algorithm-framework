---
sidebar_position: 10
---

# Deployment

Learn how to deploy your trading algorithms to production environments.

## Overview

Deploying trading algorithms requires careful consideration of infrastructure, security, monitoring, and risk management. This guide covers best practices for moving from development to production.

## Deployment Options

### 1. Local Deployment

Run your algorithm on a local machine or server:

```python
from investing_algorithm_framework import create_app

# Create production app
app = create_app(config_file="production.yaml")

# Start the algorithm
if __name__ == "__main__":
    app.start_trading()
```

**Pros:**
- Full control over environment
- Lower latency to exchanges
- Cost-effective for smaller operations

**Cons:**
- Single point of failure
- Requires manual monitoring
- Infrastructure management overhead

### 2. Cloud Deployment

Deploy to cloud platforms like AWS, Google Cloud, or Azure:

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Run the trading algorithm
CMD ["python", "main.py"]
```

**Pros:**
- High availability and scalability
- Managed infrastructure
- Built-in monitoring and logging

**Cons:**
- Higher costs
- Potential latency issues
- Vendor lock-in

### 3. VPS Deployment

Use a Virtual Private Server for dedicated resources:

```bash
# Example deployment script
#!/bin/bash

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install python3 python3-pip git -y

# Clone your trading bot
git clone https://github.com/yourusername/your-trading-bot.git
cd your-trading-bot

# Install dependencies
pip3 install -r requirements.txt

# Create systemd service
sudo systemctl enable trading-bot
sudo systemctl start trading-bot
```

## Production Configuration

### Environment Configuration

Create separate configuration files for different environments:

```yaml
# production.yaml
environment: production
debug: false

database:
  uri: "postgresql://user:pass@host:5432/trading_prod"
  
exchanges:
  binance:
    api_key: "${BINANCE_API_KEY}"
    api_secret: "${BINANCE_API_SECRET}"
    sandbox: false

portfolio:
  initial_balance: 10000
  risk_per_trade: 0.02
  max_drawdown: 0.15

logging:
  level: INFO
  file: "/var/log/trading-bot/app.log"
```

```yaml
# staging.yaml
environment: staging
debug: true

database:
  uri: "sqlite:///staging.db"
  
exchanges:
  binance:
    api_key: "${BINANCE_TESTNET_KEY}"
    api_secret: "${BINANCE_TESTNET_SECRET}"
    sandbox: true

portfolio:
  initial_balance: 1000
  risk_per_trade: 0.05
  max_drawdown: 0.20

logging:
  level: DEBUG
  file: "staging.log"
```

### Environment Variables

Use environment variables for sensitive information:

```python
import os
from investing_algorithm_framework import create_app

# Load configuration from environment
config = {
    "database_uri": os.getenv("DATABASE_URI"),
    "api_key": os.getenv("EXCHANGE_API_KEY"),
    "api_secret": os.getenv("EXCHANGE_API_SECRET"),
    "webhook_url": os.getenv("WEBHOOK_URL"),
}

app = create_app(config=config)
```

```bash
# .env file (never commit to git)
DATABASE_URI=postgresql://user:pass@localhost:5432/trading
EXCHANGE_API_KEY=your_api_key_here
EXCHANGE_API_SECRET=your_api_secret_here
WEBHOOK_URL=https://hooks.slack.com/your_webhook
```

## Security Best Practices

### API Key Management

```python
from cryptography.fernet import Fernet

class SecureConfig:
    def __init__(self):
        self.encryption_key = os.getenv("ENCRYPTION_KEY")
        self.cipher = Fernet(self.encryption_key)
    
    def decrypt_api_key(self, encrypted_key):
        return self.cipher.decrypt(encrypted_key.encode()).decode()
    
    def get_exchange_credentials(self):
        return {
            "api_key": self.decrypt_api_key(os.getenv("ENCRYPTED_API_KEY")),
            "api_secret": self.decrypt_api_key(os.getenv("ENCRYPTED_API_SECRET"))
        }
```

### Network Security

```python
# Use HTTPS and verify SSL certificates
import requests
import ssl

# Verify SSL certificates
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = True
ssl_context.verify_mode = ssl.CERT_REQUIRED

# Configure exchange with security settings
exchange_config = {
    "enableRateLimit": True,
    "timeout": 30000,
    "ssl_verify": True,
    "requests_session": requests.Session()
}
```

## Monitoring and Alerting

### Health Checks

```python
from flask import Flask, jsonify
import threading

class HealthMonitor:
    def __init__(self, app):
        self.app = app
        self.is_healthy = True
        self.last_heartbeat = datetime.now()
        
    def start_health_endpoint(self):
        """Start health check endpoint"""
        health_app = Flask(__name__)
        
        @health_app.route("/health")
        def health_check():
            return jsonify({
                "status": "healthy" if self.is_healthy else "unhealthy",
                "last_heartbeat": self.last_heartbeat.isoformat(),
                "uptime": (datetime.now() - self.app.start_time).total_seconds()
            })
        
        health_app.run(host="0.0.0.0", port=8080)
        
    def heartbeat(self):
        """Update heartbeat timestamp"""
        self.last_heartbeat = datetime.now()
```

### Logging Configuration

```python
import logging
import logging.handlers

def setup_production_logging():
    """Configure logging for production"""
    
    # Create logger
    logger = logging.getLogger("trading_bot")
    logger.setLevel(logging.INFO)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        "/var/log/trading-bot/app.log",
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    
    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
```

### Alerting System

```python
import requests
import smtplib
from email.mime.text import MIMEText

class AlertManager:
    def __init__(self, slack_webhook=None, email_config=None):
        self.slack_webhook = slack_webhook
        self.email_config = email_config
    
    def send_alert(self, message, severity="INFO"):
        """Send alert via multiple channels"""
        
        if severity == "CRITICAL":
            self.send_slack_alert(f"🚨 CRITICAL: {message}")
            self.send_email_alert(f"CRITICAL ALERT: {message}")
        elif severity == "WARNING":
            self.send_slack_alert(f"⚠️ WARNING: {message}")
        else:
            self.send_slack_alert(f"ℹ️ INFO: {message}")
    
    def send_slack_alert(self, message):
        if self.slack_webhook:
            payload = {"text": message}
            requests.post(self.slack_webhook, json=payload)
    
    def send_email_alert(self, message):
        if self.email_config:
            msg = MIMEText(message)
            msg['Subject'] = "Trading Bot Alert"
            msg['From'] = self.email_config['from']
            msg['To'] = self.email_config['to']
            
            # Send email logic here
```

## Performance Optimization

### Database Optimization

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

# Optimized database connection
engine = create_engine(
    database_uri,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

### Caching Strategy

```python
import redis
from functools import wraps

class CacheManager:
    def __init__(self, redis_url):
        self.redis_client = redis.from_url(redis_url)
    
    def cache_market_data(self, symbol, timeframe, ttl=60):
        """Cache market data with TTL"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                cache_key = f"market_data:{symbol}:{timeframe}"
                
                # Try to get from cache
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    return json.loads(cached_data)
                
                # Get fresh data and cache it
                data = func(*args, **kwargs)
                self.redis_client.setex(
                    cache_key, 
                    ttl, 
                    json.dumps(data, default=str)
                )
                return data
            return wrapper
        return decorator
```

## Disaster Recovery

### Backup Strategy

```python
import shutil
import os
from datetime import datetime

class BackupManager:
    def __init__(self, backup_dir="/backups"):
        self.backup_dir = backup_dir
        os.makedirs(backup_dir, exist_ok=True)
    
    def backup_database(self, db_path):
        """Backup database"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.backup_dir}/db_backup_{timestamp}.db"
        shutil.copy2(db_path, backup_path)
        return backup_path
    
    def backup_logs(self, log_dir):
        """Backup logs"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.backup_dir}/logs_backup_{timestamp}"
        shutil.copytree(log_dir, backup_path)
        return backup_path
```

### Recovery Procedures

```python
class RecoveryManager:
    def __init__(self, app):
        self.app = app
    
    def graceful_shutdown(self):
        """Gracefully shutdown the application"""
        
        # Cancel all open orders
        self.app.cancel_all_orders()
        
        # Save state
        self.app.save_state()
        
        # Close database connections
        self.app.close_database()
        
        print("Application shutdown complete")
    
    def emergency_stop(self):
        """Emergency stop with position closure"""
        
        # Close all positions immediately
        positions = self.app.get_positions()
        for position in positions:
            self.app.create_sell_order(
                target_symbol=position.symbol.split('/')[0],
                percentage=1.0,
                order_type="MARKET"
            )
        
        # Cancel all orders
        self.app.cancel_all_orders()
        
        print("Emergency stop executed")
```

## Deployment Checklist

### Pre-Deployment

- [ ] **Strategy Testing**: Thorough backtesting and forward testing
- [ ] **Security Review**: API keys, encryption, network security
- [ ] **Configuration**: Production config files and environment variables
- [ ] **Monitoring**: Logging, health checks, and alerting setup
- [ ] **Backup**: Database and log backup procedures
- [ ] **Documentation**: Deployment and recovery procedures

### Post-Deployment

- [ ] **Health Verification**: Confirm all systems are operational
- [ ] **Monitor Initial Trades**: Watch first few trades closely
- [ ] **Performance Baseline**: Establish performance metrics
- [ ] **Alert Testing**: Verify alerting systems work
- [ ] **Backup Testing**: Test backup and recovery procedures

## Scaling Considerations

### Horizontal Scaling

```python
# Multi-instance deployment with Redis coordination
class CoordinatedStrategy(TradingStrategy):
    def __init__(self, instance_id, redis_client):
        super().__init__()
        self.instance_id = instance_id
        self.redis_client = redis_client
    
    def apply_strategy(self, algorithm, market_data):
        # Use distributed locking
        lock_key = f"strategy_lock:{symbol}"
        
        with self.redis_client.lock(lock_key, timeout=10):
            # Strategy logic here
            pass
```

### Vertical Scaling

```python
# Resource optimization
import psutil
import gc

class ResourceManager:
    def monitor_resources(self):
        """Monitor system resources"""
        cpu_percent = psutil.cpu_percent()
        memory_percent = psutil.virtual_memory().percent
        
        if cpu_percent > 80:
            print(f"High CPU usage: {cpu_percent}%")
            
        if memory_percent > 80:
            print(f"High memory usage: {memory_percent}%")
            gc.collect()  # Force garbage collection
```

## Next Steps

With your algorithm deployed, focus on:

1. **Continuous Monitoring**: Watch performance and system health
2. **Regular Updates**: Update strategies based on market conditions
3. **Risk Management**: Monitor and adjust risk parameters
4. **Performance Analysis**: Regular strategy performance reviews

Your trading algorithm is now ready for production! Remember to start with small position sizes and gradually scale up as you gain confidence in your deployment.
