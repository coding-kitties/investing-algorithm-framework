from investing_algorithm_framework.domain.models.base_model import BaseModel
from investing_algorithm_framework.domain.models.trade.trade_risk_type import \
    TradeRiskType


class TradeTakeProfit(BaseModel):
    """
    TradeTakeProfit represents a take profit strategy for a trade.

    Attributes:
        trade: Trade - the trade that the take profit is for
        take_profit: float - the take profit percentage
        take_risk_type: TradeRiskType - the type of trade risk, either
            trailing or fixed
        percentage: float - the take profit percentage
        sell_percentage: float - the percentage of the trade to sell when the
            take profit is hit. Default is 100% of the trade. If the take profit percentage is lower than 100% a check must be made that
            the combined sell percentage of all take profits is less or
            equal than 100%.

     if trade_risk_type is fixed, the take profit price is calculated as follows:
        You buy a stock at $100.
        You set a 5% take profit, meaning you will sell if the price
            rises to $105.
        If the price rises to $120, the take profit triggers,
            and you exit with a $20 profit.
        But if the price keeps falling below $105, the take profit is not
            triggered.

    if trade_risk_type is trailing, the take profit price is calculated as follows:
        You buy a stock at $100.
        You set a 5% trailing take profit, the moment the price rises
            5% the initial take profit mark will be set. This means you
            will set the take_profit_price initially at none and
            only if the price hits $105, you will set the
            take_profit_price to $105.
        if the price drops below $105, the take profit is triggered.
        If the price rises to $120, the take profit adjusts to $114 (5% below $120).
        If the price falls to $114, the position is closed, securing a $14 profit.
        But if the price keeps rising to $150, the take profit moves up to $142.50.

    """

    def __init__(
        self,
        trade_id: int,
        take_risk_type: TradeRiskType,
        percentage: float,
        open_price: float,
        total_amount_trade: float,
        sell_percentage: float = 100,
        active: bool = True
    ):
        self.trade_id = trade_id
        self.take_risk_type = take_risk_type
        self.percentage = percentage
        self.sell_percentage = sell_percentage
        self.high_water_mark = None
        self.take_profit_price = open_price * \
            (1 + (self.percentage / 100))
        self.sell_amount = total_amount_trade * (self.sell_percentage / 100)
        self.sold_amount = 0
        self.active = active

    def has_triggered(self, current_price: float) -> bool:

        if TradeRiskType.FIXED.equals(self.take_risk_type):
            # Check if the current price is less than the high water mark
            return current_price >= self.take_profit_price
        else:

            if self.high_water_mark is None:

                if current_price < self.take_profit_price:
                    return False
                elif current_price >= self.take_profit_price:
                    take_profit_price = current_price * \
                        (1 - (self.percentage / 100))

                    if self.take_profit_price < take_profit_price:
                        self.take_profit_price = take_profit_price
                        self.high_water_mark = current_price

                return False

            # Check if the current price is less than the stop loss price
            if current_price <= self.take_profit_price:
                return True

            # Increase the high water mark and stop loss price
            elif current_price > self.high_water_mark:
                self.high_water_mark = current_price
                self.take_profit_price = self.high_water_mark * \
                    (1 - (self.percentage / 100))

        return False

    def __str__(self) -> str:
        return (
            f"TradeTakeProfit(trade_id={self.trade_id}, "
            f"take_risk_type={self.take_risk_type}, "
            f"percentage={self.percentage}, "
            f"sell_percentage={self.sell_percentage})"
            f"open_price={self.open_price}, "
            f"take_profit_price={self.take_profit_price}"
        )
