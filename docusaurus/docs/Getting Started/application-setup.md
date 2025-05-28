---

sidebar_position: 2

---

# Application Setup
The best way to get started with the framework is to create an application through the init cli command.
You can do this by running the following command in your terminal:

```bash
investing-algorithm-framework init
```

This will create the following directory structure:

```bash
.
├── README.md
├── app.py
├── strategies
│   └── my_trading_strategy.py
└── gitignore
```

The `app.py` file is the main entry point for your application. Ideally, you should only use this file to register your
strategies, portfolio configurations and market data sources. Its also
not recommended to add any logic to this file because the framework will use this file to run your application.

The `strategies` directory is where you can add your trading strategies. You can create multiple files in this directory
and add your trading strategies to them. The framework will use this directory to save and link your 
trading strategies to your backtest runs. This allows you to easily run multiple backtests with different trading strategies 
and bundle them with your backtest results. 

By default the REST API and UI are disabled. You can enable them by running the init command with the `--web` flag:

```bash
investing-algorithm-framework init --web
```

or you can enable them later by adding the following lines to your `app.py` file:

```python
import logging.config
from dotenv import load_dotenv

from investing_algorithm_framework import create_app, DEFAULT_LOGGING_CONFIG

load_dotenv()
logging.config.dictConfig(DEFAULT_LOGGING_CONFIG)

app = create_app(
    web=True,  # Enable the REST API and UI
)

# Register your trading strategies here
...

# Register your market data sources here
...

# Register your portfolio configurations here
...

# Run the app
if __name__ == "__main__":
    app.run()
```
