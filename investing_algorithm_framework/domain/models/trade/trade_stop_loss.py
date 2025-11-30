from dateutil.parser import parse
from datetime import timezone
from datetime import datetime

from investing_algorithm_framework.domain.models.base_model import BaseModel


class TradeStopLoss(BaseModel):
    """
    TradeStopLoss represents a stop loss strategy for a trade.

    if trailing is set to False, the stop loss price is calculated as follows:
        You buy a stock at $100.
        You set a 5% stop loss, meaning you will sell if
            the price drops to $95.
        If the price rises to $120, the stop loss is not triggered.
        But if the price keeps falling to $95, the stop loss triggers,
            and you exit with a $5 loss.

    if trailing is set to True, the stop loss price is
    calculated as follows:
        You buy a stock at $100.
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
        - trade (Trade): the trade that the take profit is for
        - trailing (bool): whether the stop loss is trailing or fixed
        - percentage (float): the stop loss percentage
        - sell_percentage (float): the percentage of the trade to sell when the
            take profit is hit. Default is 100% of the trade. If the
            take profit percentage is lower than 100% a check must
            be made that the combined sell percentage of all
            take profits is less or equal than 100%.
        - open_price (float): the price at which the trade was opened
        - high_water_mark_date (str): the date at which the high water mark
            was reached
        - active (bool): whether the stop loss is active
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
        self.triggered = triggered
        self.triggered_at = triggered_at
        self.sell_percentage = sell_percentage
        self.high_water_mark = high_water_mark
        self.high_water_mark_date = high_water_mark_date
        self.open_price = open_price
        self.created_at = created_at
        self.updated_at = updated_at

        if high_water_mark is None:
            self.high_water_mark = open_price
            self.stop_loss_price = self.open_price * \
                (1 - (self.percentage / 100))
            self.high_water_mark_date = created_at
        else:
            self.stop_loss_price = high_water_mark * \
                (1 - (self.percentage / 100))

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
        Function to update the take profit price based on the last
        reported price.
        The take profit price is only updated when the trade risk
        type is trailing.
        The take profit price is updated based on the current price
        and the percentage of the take profit.

        Args:
            current_price (float): the last reported price of the trade
            date (datetime): the date of the last reported price

        Returns:
            None
        """

        if not self.active or self.sold_amount == self.sell_amount:
            return

        if not self.trailing:
            # Check if the current price is less than the high water mark
            if current_price > self.high_water_mark:
                self.high_water_mark = current_price
            return
        else:
            # Check if the current price is less than the stop loss price
            if current_price <= self.stop_loss_price:
                return
            elif current_price > self.high_water_mark:
                self.high_water_mark = current_price
                self.high_water_mark_date = date
                self.stop_loss_price = self.high_water_mark * \
                    (1 - (self.percentage / 100))

    def has_triggered(self, current_price: float) -> bool:
        """
        Function to check if the stop loss has triggered.
        Function always returns False if the stop loss is not active or
            the sold amount is equal to the sell amount.

        Args:
            current_price: float - the current price of the trade

        Returns:
            bool - True if the stop loss has triggered, False otherwise
        """
        if not self.active or self.sold_amount == self.sell_amount:
            return False

        if not self.trailing:
            # Check if the current price is less than the high watermark
            return current_price <= self.stop_loss_price
        else:
            # Check if the current price is less than the stop loss price
            if current_price <= self.stop_loss_price:
                return True
            elif current_price > self.high_water_mark:
                self.high_water_mark = current_price
                self.stop_loss_price = self.high_water_mark * \
                    (1 - (self.percentage / 100))

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
        def ensure_iso(value):

            if value is None:
                return value

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
            "high_water_mark_date": self.high_water_mark_date,
            "triggered": self.triggered,
            "triggered_at": ensure_iso(getattr(self, "triggered_at", None)),
            "stop_loss_price": self.stop_loss_price,
            "sell_amount": self.sell_amount,
            "sold_amount": self.sold_amount,
            "active": self.active,
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

        return TradeStopLoss(
            trade_id=data.get("trade_id"),
            trailing=data.get("trailing"),
            percentage=data.get("percentage"),
            open_price=data.get("open_price"),
            total_amount_trade=data.get("sell_amount", 0) /
                               (data.get("sell_percentage", 100) / 100),
            sell_percentage=data.get("sell_percentage", 100),
            active=data.get("active", True),
            sell_prices=data.get("sell_prices"),
            sell_dates=data.get("sell_dates"),
            sell_amount=data.get("sell_amount"),
            high_water_mark=data.get("high_water_mark"),
            high_water_mark_date=high_water_mark_date,
            triggered=data.get("triggered", False),
            triggered_at=triggered_at,
            created_at=created_at,
            updated_at=updated_at
        )

    def __repr__(self):
        return self.repr(
            trade_id=self.trade_id,
            trailing=self.trailing,
            percentage=self.percentage,
            sell_percentage=self.sell_percentage,
            high_water_mark=self.high_water_mark,
            high_water_mark_date=self.high_water_mark_date,
            open_price=self.open_price,
            stop_loss_price=self.stop_loss_price,
            sell_amount=self.sell_amount,
            sold_amount=self.sold_amount,
            sell_prices=self.sell_prices,
            active=self.active,
            triggered=self.triggered,
            triggered_at=self.triggered_at,
            created_at=self.created_at,
            updated_at=self.updated_at
        )
