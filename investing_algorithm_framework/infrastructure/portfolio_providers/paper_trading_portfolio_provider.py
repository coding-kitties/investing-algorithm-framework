from logging import getLogger
from typing import Union

from investing_algorithm_framework.domain import PortfolioProvider, \
    Order, Position

logger = getLogger("investing_algorithm_framework")


class PaperTradingPortfolioProvider(PortfolioProvider):
    """
    Broker-agnostic paper-trading portfolio provider (see
    ``PaperTradingMode.LOCAL``/``AUTO`` fallback). There is no real
    exchange balance to reconcile against — the simulated account is
    self-funded from ``PortfolioConfiguration.initial_balance``, so
    this always reports that as the available balance and lets the
    framework's own order/position bookkeeping track everything else
    from that point on.

    Scoped to the specific market(s) it was registered for so it never
    shadows a real ``PortfolioProvider`` for a live-traded market in
    the same app.
    """

    def __init__(self, markets, priority=0):
        super().__init__(priority=priority)
        self._markets = {market.upper() for market in markets}

    def supports_market(self, market) -> bool:
        return market.upper() in self._markets

    def get_order(
        self, portfolio, order, market_credential
    ) -> Union[Order, None]:
        # Paper orders fill instantly and never exist externally —
        # the order the framework already has is authoritative.
        return order

    def get_position(
        self, portfolio, symbol, market_credential
    ) -> Union[Position, None]:
        return Position(
            symbol=symbol,
            amount=portfolio.initial_balance,
            cost=0,
            portfolio_id=portfolio.id,
        )
