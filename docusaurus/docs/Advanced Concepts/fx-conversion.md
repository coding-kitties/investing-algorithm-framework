---
sidebar_position: 4
---

# Currency / FX Conversion

When you trade across multiple markets that use different currencies, you need a way to express all position values in a single **base currency**. The framework provides a pluggable FX conversion system that handles this automatically.

## Quick Start

```python
from investing_algorithm_framework import (
    create_app, StaticFXRateProvider
)

app = create_app()

# 1. Set the base currency for portfolio reporting
app.set_base_currency("EUR")

# 2. Register an FX rate provider
app.add_fx_rate_provider(StaticFXRateProvider({
    ("USD", "EUR"): 0.92,
    ("GBP", "EUR"): 1.17,
}))

# 3. Add your markets as usual
app.add_market(
    market="binance",
    trading_symbol="USD",
    # ...
)
app.add_market(
    market="bitvavo",
    trading_symbol="EUR",
    # ...
)
```

Inside a strategy you can now call:

```python
class MyStrategy(TradingStrategy):
    def run_strategy(self, context: Context, **kwargs):
        # Total portfolio value across all markets, in EUR
        total_value = context.get_portfolio_value()

        # Convert a specific amount
        usd_amount = 1000
        eur_amount = context.convert_to_base_currency(usd_amount, "USD")

        # Get a raw FX rate
        rate = context.get_fx_rate("GBP", "EUR")
```

## Concepts

### Base Currency

The base currency is the single currency in which the total portfolio value is reported. Set it once on the app:

```python
app.set_base_currency("EUR")
```

If no base currency is set, `context.get_portfolio_value()` returns the value of the first portfolio in its own trading currency — no conversion takes place.

### FX Rate Provider

An FX rate provider is any class that implements `FXRateProvider`:

```python
from investing_algorithm_framework import FXRateProvider

class FXRateProvider(ABC):
    def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        date: datetime = None
    ) -> float:
        """Return rate such that amount_in_to = amount_in_from * rate."""
        ...
```

The `date` parameter is passed automatically during backtesting (the current simulation date) and during live trading (`datetime.now()`). This lets you build providers that look up historical rates for accurate backtesting.

### StaticFXRateProvider

A built-in provider for fixed rates. Inverse rates are computed automatically.

```python
from investing_algorithm_framework import StaticFXRateProvider

provider = StaticFXRateProvider({
    ("USD", "EUR"): 0.92,
    ("GBP", "EUR"): 1.17,
})

# Direct rate
provider.get_rate("USD", "EUR")  # 0.92

# Inverse is automatic
provider.get_rate("EUR", "USD")  # ~1.087

# Same currency always returns 1.0
provider.get_rate("EUR", "EUR")  # 1.0
```

You can also add rates dynamically:

```python
provider.add_rate("JPY", "EUR", 0.0062)
```

## Building a Custom FX Rate Provider

For production use you'll want live or historical rates. Implement `FXRateProvider` and fetch rates from your preferred source:

```python
import requests
from investing_algorithm_framework import FXRateProvider


class LiveFXRateProvider(FXRateProvider):
    """Fetch rates from an external API."""

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._cache = {}

    def get_rate(self, from_currency, to_currency, date=None):
        if from_currency == to_currency:
            return 1.0

        pair = f"{from_currency}/{to_currency}"

        if pair not in self._cache:
            # Replace with your actual API call
            resp = requests.get(
                f"https://api.example.com/fx/{pair}",
                headers={"Authorization": f"Bearer {self._api_key}"}
            )
            resp.raise_for_status()
            self._cache[pair] = resp.json()["rate"]

        return self._cache[pair]


app.add_fx_rate_provider(LiveFXRateProvider(api_key="..."))
```

## Context Methods

| Method | Description |
|--------|-------------|
| `context.get_fx_rate(from_currency, to_currency)` | Get the exchange rate between two currencies |
| `context.convert_to_base_currency(amount, from_currency)` | Convert an amount to the base currency |
| `context.get_portfolio_value()` | Total portfolio value across all markets in the base currency |

## How It Works

When `context.get_portfolio_value()` is called:

1. For each portfolio (market), the framework computes the **local value** — the sum of all position values denominated in that portfolio's `trading_symbol`.
2. If a `base_currency` and `FXRateProvider` are registered, the local value is converted to the base currency using `fx_rate_provider.get_rate(trading_symbol, base_currency)`.
3. All converted values are summed to produce the total portfolio value.

```
Portfolio "binance" (USD)          Portfolio "bitvavo" (EUR)
  BTC: 0.5 × $60,000 = $30,000      ETH: 2 × €3,000 = €6,000
  + USDT: $5,000                     + EUR cash: €1,000
  = $35,000                          = €7,000
         │                                  │
         │  × 0.92 (USD→EUR)               │  × 1.0 (same currency)
         ▼                                  ▼
      €32,200                           €7,000
                  ╲                    ╱
                    ╲                ╱
                  Total = €39,200
```
