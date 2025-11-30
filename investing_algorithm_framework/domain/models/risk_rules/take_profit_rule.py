class TakeProfitRule:
    """
    A rule that defines when to trigger a take profit based
    on a specified threshold such as a percentage gain in price or
    a fixed amount.

    if trailing is set to true, the take profit price is
    calculated as follows:
        You buy an asset at $100.
        You set a 5% take profit, meaning you will sell if the price
            rises to $105.
        If the price rises to $120, the take profit triggers,
            and you exit with a $20 profit.
        But if the price keeps falling below $105, the take profit is not
            triggered.

    if trailing is set to true, the take profit price is
    calculated as follows:
        You buy an asset at $100.
        You set a 5% trailing take profit, the moment the price rises
            5% the initial take profit mark will be set. This means you
            will set the take_profit_price initially at none and
            only if the price hits $105, you will set the
            take_profit_price to $105.
        if the price drops below $105, the take profit is triggered.
        If the price rises to $120, the take profit adjusts to
        $114 (5% below $120).
        If the price falls to $114, the position is closed,
        securing a $14 profit.
        But if the price keeps rising to $150, the take profit
        moves up to $142.50.


    Attributes:
        - percentage_threshold (float): The percentage gain in price
            that triggers the stop loss.
        - trailing (bool): Indicates whether the take profit is trailing
            or fixed.
        - sell_percentage (float): The percentage of the position to sell
            when the take profit is triggered.
        - symbol (str): The symbol of the asset the take profit rule
            applies to. Symbol is defined as only the target symbol.
            So for example, 'BTC' in 'BTC-EUR' or 'META' in 'META-USD'.
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
