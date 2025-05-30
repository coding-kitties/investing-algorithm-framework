---
id: application-setup
title: Create an app instance
sidebar_label: application setup
---

##  🔧 Application Setup through CLI: Command Line Interface
The CLI tool included with the framework allows you to initialize new apps with different presets


The best way to get started with the framework is to create an application through the init cli command.
You can do this by running the following command in your terminal:

### ⚙️ init Command
```bash
investing-algorithm-framework init --type default --path ./my-app --replace
```

| Option      | Type   | Description                                                             |
| ----------- | ------ | ----------------------------------------------------------------------- |
| `--type`    | `str`  | Type of app to initialize (`default`, `default_web`, `azure_function`). |
| `--path`    | `str`  | Directory path to create the app in.                                    |
| `--replace` | `bool` | If `True`, existing files will be overwritten.                          |


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

## 🏗️ Using the `create_app` Function

### Description

The `create_app` function is a factory method for creating and configuring an `App` instance. It loads environment variables, sets up the dependency container, and optionally initializes a web-based configuration.
This function is usefull if you want to create an app programmatically or if you want to extend the app with custom configurations.

### Function Signature

```python
def create_app(
    config: dict = None,
    state_handler=None,
    web: bool = False,
    name=None
) -> App:
```

| Name            | Type     | Description                                                |
| --------------- | -------- | ---------------------------------------------------------- |
| `config`        | `dict`   | Optional dictionary containing app configuration.          |
| `state_handler` | `object` | Optional custom state handler for managing internal state. |
| `web`           | `bool`   | Whether to configure the app for web use (`AppMode.WEB`).  |
| `name`          | `str`    | Optional name to assign to the application instance.       |

### Returns
Returns an instance of the App class, fully initialized and ready to run or extend.

### Example
```python
from investing_algorithm_framework import create_app

app = create_app(
    config={"MY_CONFIG": "value"},
    web=True,
    name="my_trading_bot"
)
```