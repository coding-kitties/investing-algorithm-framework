import os

from dateutil.parser import parse

from investing_algorithm_framework.domain.exceptions import \
    ImproperlyConfigured
from investing_algorithm_framework.domain.models.base_model import BaseModel
from investing_algorithm_framework.domain.models.portfolio.position_mode \
    import PositionMode
from investing_algorithm_framework.domain.models.portfolio\
    .paper_trading_mode import PaperTradingMode


class PortfolioConfiguration(BaseModel):
    """
    This class represents a portfolio configuration. It is used to
    configure the portfolio that the user wants to create.

    Attributes:
    - market: The market where the portfolio will be created. Falls
      back to the ``MARKET`` environment variable when not given.
    - trading_symbol: The trading symbol of the portfolio. Falls back
      to the ``TRADING_SYMBOL`` environment variable when not given.
    - track_from: The date from which the portfolio will be tracked
    - identifier: The identifier of the portfolio
    - initial_balance: The initial balance of the portfolio. Falls
      back to the ``INITIAL_BALANCE`` environment variable when not
      given.
    - paper_trading: When True, no real orders are ever placed. See
      ``PaperTradingMode`` for how execution is simulated.

    For backtesting, a portfolio configuration is used to create a
    portfolio that will be used to simulate the trading of the algorithm. if
    the user does not provide an initial balance, the portfolio will be created
    with a balance of according to the initial balanace of
        the PortfolioConfiguration class.
    """

    def __init__(
        self,
        market=None,
        trading_symbol=None,
        track_from=None,
        identifier=None,
        initial_balance=None,
        fee_percentage=0.0,
        slippage_percentage=0.0,
        deposit_schedule=None,
        position_mode=PositionMode.NETTING,
        paper_trading=False,
        paper_trading_mode=PaperTradingMode.AUTO,
    ):
        if market is None:
            market = os.getenv("MARKET")

        if trading_symbol is None:
            trading_symbol = os.getenv("TRADING_SYMBOL")

        if initial_balance is None:
            initial_balance = self._initial_balance_from_env()

        self._market = market

        if self._market is not None:
            self._market = self._market.upper()

        if self._market is None:
            raise ImproperlyConfigured(
                "Portfolio configuration requires a market. Pass "
                "market=... or set the MARKET environment variable."
            )

        self._track_from = None
        self._identifier = identifier
        self._initial_balance = initial_balance
        self._fee_percentage = fee_percentage or 0.0
        self._slippage_percentage = slippage_percentage or 0.0
        self._deposit_schedule = list(deposit_schedule or [])
        self._position_mode = PositionMode(position_mode)
        self._paper_trading = bool(paper_trading)
        self._paper_trading_mode = PaperTradingMode(paper_trading_mode)

        if trading_symbol is None:
            raise ImproperlyConfigured(
                "Portfolio configuration requires a trading symbol. Pass "
                "trading_symbol=... or set the TRADING_SYMBOL "
                "environment variable."
            )

        self._trading_symbol = trading_symbol.upper()

        if self._paper_trading and self._initial_balance is None:
            raise ImproperlyConfigured(
                "Paper trading requires an initial_balance (there is no "
                "real exchange balance to seed the simulated portfolio "
                "from). Pass initial_balance=... or set the "
                "INITIAL_BALANCE environment variable."
            )

        if self.identifier is None:
            self._identifier = self._market
        else:
            self._identifier = identifier.upper()

        if track_from:
            self._track_from = parse(track_from)

    @staticmethod
    def _initial_balance_from_env():
        value = os.getenv("INITIAL_BALANCE")

        if value is None:
            return None

        try:
            return float(value)
        except ValueError:
            raise ImproperlyConfigured(
                f"INITIAL_BALANCE environment variable {value!r} is not "
                f"a valid number"
            )

    @property
    def market(self):

        if hasattr(self._market, "upper"):
            return self._market.upper()

        return self._market

    @property
    def track_from(self):
        return self._track_from

    @property
    def identifier(self):
        return self._identifier

    @property
    def trading_symbol(self):
        return self._trading_symbol

    @property
    def initial_balance(self):
        return self._initial_balance

    @property
    def fee_percentage(self):
        return self._fee_percentage

    @property
    def slippage_percentage(self):
        return self._slippage_percentage

    @property
    def deposit_schedule(self):
        return list(self._deposit_schedule)

    @property
    def position_mode(self):
        return self._position_mode

    @property
    def paper_trading(self):
        return self._paper_trading

    @property
    def paper_trading_mode(self):
        return self._paper_trading_mode

    @property
    def has_initial_balance(self):
        return self._initial_balance is not None

    def to_dict(self):
        return {
            "market": self.market,
            "trading_symbol": self.trading_symbol,
            "track_from": self.track_from.isoformat()
            if self.track_from is not None else None,
            "identifier": self.identifier,
            "initial_balance": self.initial_balance,
            "fee_percentage": self.fee_percentage,
            "slippage_percentage": self.slippage_percentage,
            "deposit_schedule": self.deposit_schedule,
            "position_mode": self.position_mode.value,
            "paper_trading": self.paper_trading,
            "paper_trading_mode": self.paper_trading_mode.value,
        }

    @staticmethod
    def from_dict(data):
        return PortfolioConfiguration(
            market=data.get("market"),
            trading_symbol=data.get("trading_symbol"),
            track_from=data.get("track_from"),
            identifier=data.get("identifier"),
            initial_balance=data.get("initial_balance"),
            fee_percentage=data.get("fee_percentage", 0.0),
            slippage_percentage=data.get("slippage_percentage", 0.0),
            deposit_schedule=data.get("deposit_schedule"),
            position_mode=data.get("position_mode", PositionMode.NETTING),
            paper_trading=data.get("paper_trading", False),
            paper_trading_mode=data.get(
                "paper_trading_mode", PaperTradingMode.AUTO
            ),
        )

    def __eq__(self, other):
        if not isinstance(other, PortfolioConfiguration):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self):
        return self.repr(
            market=self.market,
            trading_symbol=self.trading_symbol,
            identifier=self.identifier,
            track_from=self.track_from,
            initial_balance=self.initial_balance,
            position_mode=self.position_mode,
            paper_trading=self.paper_trading,
        )
