from investing_algorithm_framework.domain.models.base_model import BaseModel
from investing_algorithm_framework.domain.models.trade.trade_risk_type import \
    TradeRiskType


class TradeTakeProfit(BaseModel):
    """
    TradeTakeProfit represents a take profit strategy for a trade.

    Attributes:
        trade: Trade - the trade that the take profit is for
        take_profit: float - the take profit percentage
        trade_risk_type: TradeRiskType - the type of trade risk, either
            trailing or fixed
        percentage: float - the take profit percentage
        sell_percentage: float - the percentage of the trade to sell when the
            take profit is hit. Default is 100% of the trade.
            If the take profit percentage is lower than 100% a check
            must be made that the combined sell percentage of
            all take profits is less or equal than 100%.

    if trade_risk_type is fixed, the take profit price is
    calculated as follows:
        You buy a stock at $100.
        You set a 5% take profit, meaning you will sell if the price
            rises to $105.
        If the price rises to $120, the take profit triggers,
            and you exit with a $20 profit.
        But if the price keeps falling below $105, the take profit is not
            triggered.

    if trade_risk_type is trailing, the take profit price is
    calculated as follows:
        You buy a stock at $100.
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
    """

    def __init__(
        self,
        trade_id: int,
        trade_risk_type: TradeRiskType,
        percentage: float,
        open_price: float,
        total_amount_trade: float,
        sell_percentage: float = 100,
        active: bool = True,
        sell_prices: str = None,
        sell_dates: str = None,
        high_water_mark_date: str = None,
    ):
        self.trade_id = trade_id
        self.trade_risk_type = trade_risk_type
        self.percentage = percentage
        self.sell_percentage = sell_percentage
        self.high_water_mark = None
        self.high_water_mark_date = high_water_mark_date
        self.open_price = open_price
        self.take_profit_price = open_price * \
            (1 + (self.percentage / 100))
        self.sell_amount = total_amount_trade * (self.sell_percentage / 100)
        self.sold_amount = 0
        self.active = active
        self.sell_prices = sell_prices
        self.sell_dates = sell_dates

    def update_with_last_reported_price(self, current_price: float, date):
        """
        Function to update the take profit price based on
            the last reported price.
        The take profit price is only updated when the
            trade risk type is trailing.
        The take profit price is updated based on the
            current price and the percentage of the take profit.

        Args:
            current_price: float - the last reported price of the trade
        """

        # Do nothing for fixed take profit
        if TradeRiskType.FIXED.equals(self.trade_risk_type):

            if self.high_water_mark is not None:
                if current_price > self.high_water_mark:
                    self.high_water_mark = current_price
                    self.high_water_mark_date = date
            else:
                if current_price >= self.take_profit_price:
                    self.high_water_mark = current_price
                    self.high_water_mark_date = date
                return

            return
        else:

            if self.high_water_mark is None:

                if current_price >= self.take_profit_price:
                    self.high_water_mark = current_price
                    self.high_water_mark_date = date
                    new_take_profit_price = self.high_water_mark * \
                        (1 - (self.percentage / 100))

                    if self.take_profit_price <= new_take_profit_price:
                        self.take_profit_price = new_take_profit_price

                return

            # Check if the current price is less than the take profit price
            if current_price < self.take_profit_price:
                return

            # Increase the high water mark and take profit price
            elif current_price > self.high_water_mark:
                self.high_water_mark = current_price
                self.high_water_mark_date = date
                new_take_profit_price = self.high_water_mark * \
                    (1 - (self.percentage / 100))

                # Only increase the take profit price if the new take
                # profit price based on the new high water mark is higher
                # then the current take profit price
                if self.take_profit_price <= new_take_profit_price:
                    self.take_profit_price = new_take_profit_price

        return

    def has_triggered(self, current_price: float = None) -> bool:

        if TradeRiskType.FIXED.equals(self.trade_risk_type):
            # Check if the current price is less than the high water mark
            return current_price >= self.take_profit_price
        else:
            # Always return false, when the high water mark is not set
            # But check if we can set the high water mark
            if self.high_water_mark is None:

                if current_price >= self.take_profit_price:
                    self.high_water_mark = current_price
                    new_take_profit_price = self.high_water_mark * \
                        (1 - (self.percentage / 100))
                    if self.take_profit_price <= new_take_profit_price:
                        self.take_profit_price = new_take_profit_price

                return False

            # Check if the current price is less than the take profit price
            if current_price < self.take_profit_price:
                return True

            # Increase the high watermark and take profit price
            elif current_price > self.high_water_mark:
                self.high_water_mark = current_price
                new_take_profit_price = self.high_water_mark * \
                    (1 - (self.percentage / 100))

                # Only increase the take profit price if the new take
                # profit price based on the new high water mark is higher
                # then the current take profit price
                if self.take_profit_price <= new_take_profit_price:
                    self.take_profit_price = new_take_profit_price

        return False

    def get_sell_amount(self) -> float:
        """
        Function to calculate the amount to sell based on the
        sell percentage and the remaining amount of the trade.
        Keep in mind the moment the take profit triggers, the remaining
            amount of the trade is used to calculate the sell amount.
        If the remaining amount is smaller than the trade amount, the
            trade stop loss stays active. The client that uses the
            trade stop loss is responsible for setting the trade stop
            loss to inactive.

        Args:
            trade: Trade - the trade to calculate the sell amount for

        """

        if not self.active:
            return 0

        return self.sell_amount - self.sold_amount

    def add_sell_price(self, price: float, date: str):
        """
        Function to add a sell price to the list of sell prices.
        The sell price is added to the list of sell prices and the
        date is added to the list of sell dates.

        Args:
            price: float - the price at which the trade was sold
            date: str - the date at which the trade was sold

        Returns:
            None
        """
        if self.sell_prices is None:
            self.sell_prices = str(price)
            self.sell_dates = str(date)
        else:
            self.sell_prices += f", {price}"
            self.sell_dates += f", {date}"

    def remove_sell_price(self, price: float, date: str):
        """
        Function to remove a sell price from the list of sell prices.
        The sell price is removed from the list of sell prices and the
        date is removed from the list of sell dates.

        Args:
            price: float - the price at which the trade was sold
            date: str - the date at which the trade was sold

        Returns:
            None
        """
        if self.sell_prices is not None:

            # Split the sell prices into a list and convert to float
            sell_prices_list = self.sell_prices.split(", ")
            sell_prices_list = [float(p) for p in sell_prices_list]

            if price in sell_prices_list:
                sell_prices_list.remove(price)
                self.sell_prices = ", ".join(sell_prices_list)

            if self.sell_prices == "":
                self.sell_prices = None

            # Split the sell dates into a list
            sell_dates_list = self.sell_dates.split(", ")
            if date in sell_dates_list:
                sell_dates_list.remove(date)
                self.sell_dates = ", ".join(sell_dates_list)
        else:
            self.sell_prices = None
            self.sell_dates = None

    def to_dict(self, datetime_format=None):
        return {
            "trade_id": self.trade_id,
            "trade_risk_type": self.trade_risk_type,
            "percentage": self.percentage,
            "open_price": self.open_price,
            "sell_percentage": self.sell_percentage,
            "high_water_mark": self.high_water_mark,
            "take_profit_price": self.take_profit_price,
            "sell_amount": self.sell_amount,
            "sold_amount": self.sold_amount,
            "active": self.active,
            "sell_prices": self.sell_prices
        }

    def __repr__(self):
        return self.repr(
            trade_id=self.trade_id,
            trade_risk_type=self.trade_risk_type,
            percentage=self.percentage,
            open_price=self.open_price,
            sell_percentage=self.sell_percentage,
            high_water_mark=self.high_water_mark,
            take_profit_price=self.take_profit_price,
            sell_amount=self.sell_amount,
            sold_amount=self.sold_amount,
            active=self.active,
            sell_prices=self.sell_prices
        )
