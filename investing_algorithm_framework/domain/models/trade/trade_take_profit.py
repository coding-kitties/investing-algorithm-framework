from datetime import timezone, datetime
from dateutil.parser import parse

from investing_algorithm_framework.domain.models.base_model import BaseModel


class TradeTakeProfit(BaseModel):
    """
    TradeTakeProfit represents a take profit strategy for a trade.

    if trailing is set to False, the take profit price is
    calculated as follows:
        You buy a stock at $100.
        You set a 5% take profit, meaning you will sell if the price
            rises to $105.
        If the price rises to $120, the take profit triggers,
            and you exit with a $20 profit.
        But if the price keeps falling below $105, the take profit is not
            triggered.

    if trailing is set to True, the take profit price is
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

    Attributes:
        - trade (Trade): the trade that the take profit is for
        - trailing (bool): whether the take profit is trailing or fixed
        - percentage (float): the stop loss percentage
        - sell_percentage (float): the percentage of the trade to sell when the
            take profit is hit. Default is 100% of the trade. If the
            take profit percentage is lower than 100% a check must
            be made that the combined sell percentage of all
            take profits is less or equal than 100%.
        - open_price (float): the price at which the trade was opened
        - take_profit_price (float): the price at which the take profit
            triggers
        - high_water_mark_date (str): the date at which the high water mark
            was reached
        - active (bool): whether the take profit is active
        - triggered (bool): whether the take profit has been triggered
        - sell_amount (float): the amount to sell when the stop loss triggers
        - sold_amount (float): the amount that has been sold
        - high_water_mark (float) the highest price of the trade
        - stop_loss_price (float) the price at which the stop loss triggers
    """

    def __init__(
        self,
        trade_id: int,
        percentage: float,
        open_price: float,
        trailing: bool = False,
        total_amount_trade: float = None,
        sell_percentage: float = 100,
        active: bool = True,
        triggered: bool = False,
        triggered_at: datetime = None,
        sell_prices: str = None,
        sell_dates: str = None,
        sell_amount: float = None,
        high_water_mark: float = None,
        high_water_mark_date: str = None,
        created_at: datetime = None,
        updated_at: datetime = None
    ):
        self.trade_id = trade_id
        self.trailing = trailing
        self.percentage = percentage
        self.sell_percentage = sell_percentage
        self.triggered = triggered
        self.triggered_at = triggered_at
        self.high_water_mark = high_water_mark
        self.high_water_mark_date = high_water_mark_date
        self.open_price = open_price
        self.created_at = created_at
        self.updated_at = updated_at

        if high_water_mark is None and not self.trailing:
            self.take_profit_price = self.open_price * \
                (1 + (self.percentage / 100))
        else:
            self.take_profit_price = None

        if sell_amount is not None:
            self.sell_amount = sell_amount
        else:
            self.sell_amount = total_amount_trade * \
                (self.sell_percentage / 100)
        self.sold_amount = 0
        self.active = active
        self.sell_prices = sell_prices
        self.sell_dates = sell_dates

    def update_with_last_reported_price(self, current_price: float, date):
        """
        Function to update the take profit price based on
            the last reported price.
        For fixed take profits: track the high water mark when price
            exceeds the take profit price.
        For trailing take profits: update the take profit price based on
            the current price and the percentage of the take profit.

        Args:
            current_price: float - the last reported price of the trade
            date: the date of the price update
        """

        if not self.trailing:
            # Fixed take profit: track high watermark
            if current_price >= self.take_profit_price:
                if (self.high_water_mark is None
                        or current_price > self.high_water_mark):
                    self.high_water_mark = current_price
                    self.high_water_mark_date = date
            return

        # Trailing take profit logic
        if self.high_water_mark is None:
            # High water mark not set yet
            # Calculate the initial take profit threshold
            initial_threshold = self.open_price * (1 + (self.percentage / 100))

            # Wait for price to reach the initial take profit threshold
            if current_price >= initial_threshold:
                # Initial threshold reached, set high watermark
                self.high_water_mark = current_price
                self.high_water_mark_date = date
                # Calculate new take profit price based on high watermark
                self.take_profit_price = self.high_water_mark * \
                    (1 - (self.percentage / 100))
        else:
            # High watermark is set, check for updates
            # Check if price has risen above high watermark (adjust upward)
            if current_price > self.high_water_mark:
                self.high_water_mark = current_price
                self.high_water_mark_date = date
                # Recalculate take profit price based on new high water mark
                new_take_profit_price = self.high_water_mark * \
                    (1 - (self.percentage / 100))
                # Update take profit price if it's higher than current
                if new_take_profit_price > self.take_profit_price:
                    self.take_profit_price = new_take_profit_price

    def has_triggered(self, current_price: float = None) -> bool:

        if not self.trailing:
            # Fixed take profit: trigger when price reaches take_profit_price
            return current_price >= self.take_profit_price
        else:
            # Trailing take profit logic
            if self.high_water_mark is None:
                # High water mark not set yet
                # Calculate the initial take profit threshold
                # (open_price * (1 + percentage))
                initial_threshold = (self.open_price
                                     * (1 + (self.percentage / 100)))

                # Wait for price to reach the initial take profit threshold
                if current_price >= initial_threshold:
                    # Initial threshold reached, set high water mark
                    self.high_water_mark = current_price
                    # Calculate new take profit price based on high water mark
                    # This is the pullback level
                    # (high_water_mark * (1 - percentage))
                    self.take_profit_price = self.high_water_mark * \
                        (1 - (self.percentage / 100))
                # Don't trigger yet, wait for pullback
                return False
            else:
                # High watermark is set, check for triggers and updates

                # Check if price has pulled back below take profit
                # price (trigger condition)
                if current_price < self.take_profit_price:
                    return True

                # Check if price has risen above high
                # water mark (adjust upward)
                if current_price > self.high_water_mark:
                    self.high_water_mark = current_price
                    # Recalculate take profit price based on
                    # new high water mark
                    new_take_profit_price = self.high_water_mark * \
                        (1 - (self.percentage / 100))
                    # Update take profit price if it's higher than current
                    if new_take_profit_price > self.take_profit_price:
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

        Returns:
            float - the amount to sell
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
            price (float): the price at which the trade was sold
            date (datetime): the date at which the trade was sold

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
        def ensure_iso(value):
            if hasattr(value, "isoformat"):
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                return value.isoformat()
            return value

        return {
            "trade_id": self.trade_id,
            "trailing": self.trailing,
            "percentage": self.percentage,
            "open_price": self.open_price,
            "sell_percentage": self.sell_percentage,
            "high_water_mark": self.high_water_mark,
            "take_profit_price": self.take_profit_price,
            "sell_amount": self.sell_amount,
            "sold_amount": self.sold_amount,
            "active": self.active,
            "triggered": self.triggered,
            "triggered_at": ensure_iso(self.triggered_at),
            "high_water_mark_date": self.high_water_mark_date,
            "sell_prices": self.sell_prices,
            "created_at": ensure_iso(self.created_at),
            "updated_at": ensure_iso(self.updated_at)
        }

    @staticmethod
    def from_dict(data: dict):
        created_at = parse(data["created_at"]) \
            if data.get("created_at") is not None else None
        updated_at = parse(data["updated_at"]) \
            if data.get("updated_at") is not None else None
        triggered_at = parse(data["triggered_at"]) \
            if data.get("triggered_at") is not None else None
        high_water_mark_date = parse(data.get("high_water_mark_date")) \
            if data.get("high_water_mark_date") is not None else None

        # Make sure all the dates are timezone utc aware
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if updated_at and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        if triggered_at and triggered_at.tzinfo is None:
            triggered_at = triggered_at.replace(tzinfo=timezone.utc)
        if high_water_mark_date and high_water_mark_date.tzinfo is None:
            high_water_mark_date = high_water_mark_date.replace(
                tzinfo=timezone.utc
            )

        return TradeTakeProfit(
            trade_id=data.get("trade_id"),
            trailing=data.get("trailing"),
            percentage=data.get("percentage"),
            open_price=data.get("open_price"),
            total_amount_trade=data.get("total_amount_trade"),
            sell_percentage=data.get("sell_percentage", 100),
            active=data.get("active", True),
            triggered=data.get("triggered", False),
            triggered_at=triggered_at,
            sell_prices=data.get("sell_prices"),
            sell_dates=data.get("sell_dates"),
            sell_amount=data.get("sell_amount"),
            high_water_mark=data.get("high_water_mark"),
            high_water_mark_date=high_water_mark_date,
            created_at=created_at,
            updated_at=updated_at
        )

    def __repr__(self):
        return self.repr(
            trade_id=self.trade_id,
            trailing=self.trailing,
            percentage=self.percentage,
            open_price=self.open_price,
            sell_percentage=self.sell_percentage,
            high_water_mark=self.high_water_mark,
            high_water_mark_date=self.high_water_mark_date,
            triggered=self.triggered,
            triggered_at=self.triggered_at,
            take_profit_price=self.take_profit_price,
            sell_amount=self.sell_amount,
            sold_amount=self.sold_amount,
            active=self.active,
            sell_prices=self.sell_prices,
            created_at=self.created_at,
            updated_at=self.updated_at
        )
