from enum import Enum


class PaperTradingMode(str, Enum):
    """
    How a paper-traded portfolio should simulate order execution.

    - ``AUTO``: prefer the broker's own sandbox/testnet if the
      registered ``OrderExecutor``/``PortfolioProvider`` for the
      market support it (see ``supports_sandbox_mode``); otherwise
      fall back to the framework's local paper-trading simulator.
    - ``BROKER``: require the broker's native sandbox/testnet. Raises
      an ``OperationalException`` at startup if the market's executor
      or provider doesn't support it — never silently falls back.
    - ``LOCAL``: always use the framework's local paper-trading
      simulator, regardless of what the broker supports. No real
      network calls are made to place orders.
    """
    AUTO = "auto"
    BROKER = "broker"
    LOCAL = "local"
