class TradingCost:
    """
    A cost model for trading a specific symbol.

    Defines the fee and slippage that apply when buying or selling
    an asset during backtests. Can be attached per-symbol on a
    TradingStrategy (overrides market-level defaults) or set as
    market-level defaults on PortfolioConfiguration / app.add_market().

    Slippage can be specified either as a flat percentage
    (``slippage_percentage``) or via a pluggable ``slippage_model``
    (e.g. ``VolumeShareSlippage``, ``FixedBasisPointsSlippage``).
    When both are provided, ``slippage_model`` takes precedence.

    Attributes:
        symbol (str): The target symbol this cost applies to
            (e.g. "BTC"). Use ``None`` for market-level defaults.
        fee_percentage (float): Fee as a percentage of trade value.
            Default 0.0. Example: 0.1 means 0.1 % fee.
        slippage_percentage (float): Slippage as a percentage of
            price. Default 0.0. Buy fills higher, sell fills lower.
        fee_fixed (float): Fixed fee per trade in the trading
            currency. Default 0.0.
        slippage_model: Optional pluggable ``SlippageModel`` instance.
            When set, overrides ``slippage_percentage``.
    """

    def __init__(
        self,
        symbol=None,
        fee_percentage=0.0,
        slippage_percentage=0.0,
        fee_fixed=0.0,
        slippage_model=None,
    ):
        self.symbol = symbol.upper() if symbol else None
        self.fee_percentage = fee_percentage
        self.slippage_percentage = slippage_percentage
        self.fee_fixed = fee_fixed
        self.slippage_model = slippage_model

    def get_buy_fill_price(self, price, amount=None, volume=None):
        """Return the slippage-adjusted buy fill price."""
        if self.slippage_model is not None:
            return self.slippage_model.calculate_slippage(
                price, "BUY", amount=amount, volume=volume,
            )
        return price * (1 + self.slippage_percentage / 100)

    def get_sell_fill_price(self, price, amount=None, volume=None):
        """Return the slippage-adjusted sell fill price."""
        if self.slippage_model is not None:
            return self.slippage_model.calculate_slippage(
                price, "SELL", amount=amount, volume=volume,
            )
        return price * (1 - self.slippage_percentage / 100)

    def get_max_fill_amount(self, order_amount, volume=None):
        """Return the maximum fillable amount for this bar.

        Delegates to the slippage model's ``max_fill_amount`` when
        a model is configured; otherwise returns the full
        ``order_amount`` (no volume limit).
        """
        if self.slippage_model is not None:
            return self.slippage_model.max_fill_amount(
                order_amount, volume=volume,
            )
        return order_amount

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
