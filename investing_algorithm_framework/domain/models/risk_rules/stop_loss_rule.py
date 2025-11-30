class StopLossRule:
    """
    A rule that defines when to trigger a stop loss based
    on a specified threshold such as a percentage drop in price or
    a fixed amount.

    if trade_risk_type is fixed, the stop loss price is calculated as follows:
        You buy an asset at $100.
        You set a 5% stop loss, meaning you will sell if
            the price drops to $95.
        If the price rises to $120, the stop loss is not triggered.
        But if the price keeps falling to $95, the stop loss triggers,
            and you exit with a $5 loss.

    if trade_risk_type is trailing, the stop loss price is
    calculated as follows:
        You buy an asset at $100.
        You set a 5% trailing stop loss, meaning you will sell if
            the price drops 5% from its peak at $96
        If the price rises to $120, the stop loss adjusts
            to $114 (5% below $120).
        If the price falls to $114, the position is
            closed, securing a $14 profit.
        But if the price keeps rising to $150, the stop
            loss moves up to $142.50.
        If the price drops from $150 to $142.50, the stop
            loss triggers, and you exit with a $42.50 profit.

    Attributes:
        - percentage_threshold (float): The percentage drop in price
            that triggers the stop loss.
        - trailing (bool): Indicates whether the stop loss is trailing
            or fixed.
        - sell_percentage (float): The percentage of the position to sell
            when the stop loss is triggered.
        - symbol (str): The symbol of the asset the stop loss rule
            applies to. Symbol is defined as the target symbol
            (the asset being traded) combined with the trading symbol
            (the asset used to trade the target symbol), e.g., 'BTC-EUR'.
    """
    def __init__(
        self,
        percentage_threshold: float,
        sell_percentage: float,
        symbol: str,
        trailing: bool = False,
    ):
        self.percentage_threshold = percentage_threshold
        self.trailing = trailing
        self.sell_percentage = sell_percentage
        self.symbol = symbol
