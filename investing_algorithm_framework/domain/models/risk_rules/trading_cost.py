class TradingCost:
    """
    A cost model for trading a specific symbol.

    Defines the fee and slippage that apply when buying or selling
    an asset during backtests. Can be attached per-symbol on a
    TradingStrategy (overrides market-level defaults) or set as
    market-level defaults on PortfolioConfiguration / app.add_market().

    Attributes:
        symbol (str): The target symbol this cost applies to
            (e.g. "BTC"). Use ``None`` for market-level defaults.
        fee_percentage (float): Fee as a percentage of trade value.
            Default 0.0. Example: 0.1 means 0.1 % fee.
        slippage_percentage (float): Slippage as a percentage of
            price. Default 0.0. Buy fills higher, sell fills lower.
        fee_fixed (float): Fixed fee per trade in the trading
            currency. Default 0.0.
    """

    def __init__(
        self,
        symbol=None,
        fee_percentage=0.0,
        slippage_percentage=0.0,
        fee_fixed=0.0,
    ):
        self.symbol = symbol.upper() if symbol else None
        self.fee_percentage = fee_percentage
        self.slippage_percentage = slippage_percentage
        self.fee_fixed = fee_fixed

    def get_buy_fill_price(self, price):
        """Return the slippage-adjusted buy fill price."""
        return price * (1 + self.slippage_percentage / 100)

    def get_sell_fill_price(self, price):
        """Return the slippage-adjusted sell fill price."""
        return price * (1 - self.slippage_percentage / 100)

    def get_fee(self, trade_value):
        """Return the fee for a given trade value."""
        return trade_value * self.fee_percentage / 100 + self.fee_fixed

    @staticmethod
    def resolve(symbol, trading_costs, portfolio_configuration=None):
        """
        Resolve the effective TradingCost for *symbol*.

        Priority:
            1. Per-symbol TradingCost on the strategy
            2. Market-level defaults from PortfolioConfiguration
            3. Zero-cost fallback

        Args:
            symbol: Target symbol (e.g. "BTC").
            trading_costs: List[TradingCost] from the strategy.
            portfolio_configuration: Optional PortfolioConfiguration
                with market-level fee/slippage defaults.

        Returns:
            TradingCost instance to use.
        """
        if trading_costs:
            for tc in trading_costs:
                if tc.symbol and tc.symbol == symbol.upper():
                    return tc

        # Fall back to market-level defaults
        if portfolio_configuration is not None:
            fee_pct = getattr(
                portfolio_configuration, 'fee_percentage', 0.0
            ) or 0.0
            slip_pct = getattr(
                portfolio_configuration, 'slippage_percentage', 0.0
            ) or 0.0

            if fee_pct or slip_pct:
                return TradingCost(
                    symbol=symbol,
                    fee_percentage=fee_pct,
                    slippage_percentage=slip_pct,
                )

        return _ZERO_COST


# Singleton zero-cost instance (avoids allocations)
_ZERO_COST = TradingCost()
