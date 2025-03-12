import logging

from investing_algorithm_framework.domain import OrderStatus, OrderSide, \
    TradeStatus

logger = logging.getLogger(__name__)


class PerformanceService:
    """
    Service to calculate the performance of a portfolio.
    """

    def __init__(
        self,
        order_repository,
        position_repository,
        portfolio_repository,
        trade_repository,
    ):
        self.order_repository = order_repository
        self.position_repository = position_repository
        self.portfolio_repository = portfolio_repository
        self.trade_repository = trade_repository

    def get_total_net_gain(self, portfolio_id):
        pass

    def get_total_size(self, portfolio_id):
        pass

    def get_percentage_change(self, portfolio_id, time_frame):
        pass

    def get_total_cost(self, portfolio_id):
        pass

    def get_number_of_trades_closed(self, portfolio_id):
        """"
        Get the number of trades closed. This function will
        return the number of trades that are already closed.

        param portfolio_id: The id of the portfolio
        type portfolio_id: str

        return: The number of trades closed
        """
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        return self.trade_repository.count(
            {"portfolio_id": portfolio.id, "status": TradeStatus.OPEN.value}
        )

    def get_number_of_trades_open(self, portfolio_id):
        """
        Get the number of trades open. This function will
        return the number of trades that are still open.

        param portfolio_id: The id of the portfolio
        type portfolio_id: str

        return: The number of trades open
        """
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        return self.trade_repository.count(
            {"portfolio_id": portfolio.id, "status": TradeStatus.OPEN.value}
        )

    def get_percentage_positive_trades(self, portfolio_id):
        """
        Get the percentage of positive trades. This function will
        calculate the percentage of positive trades by dividing the
        total number of positive trades by the total number of trades
        and then multiplying it by 100.

        param portfolio_id: The id of the portfolio
        type portfolio_id: str

        return: The percentage of positive trades
        """
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        trades = self.trade_repository.get_all(
            {"portfolio_id": portfolio.id, "status": OrderStatus.CLOSED.value}
        )
        total_number_of_trades = len(trades)

        if total_number_of_trades == 0:
            return 0.0

        positive_trades = [
            trade for trade in trades if trade.net_gain > 0
        ]
        total_number_of_positive_trades = len(positive_trades)
        return total_number_of_positive_trades / total_number_of_trades * 100

    def get_percentage_negative_trades(self, portfolio_id):
        """
        Get the percentage of negative trades. This function will
        calculate the percentage of negative trades by dividing the
        total number of negative trades by the total number of trades
        and then multiplying it by 100.

        param portfolio_id: The id of the portfolio
        type portfolio_id: str

        return: The percentage of negative trades
        """

        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        trades = self.trade_repository.get_all(
            {"portfolio_id": portfolio.id, "status": TradeStatus.CLOSED.value}
        )
        total_number_of_trades = len(trades)

        if total_number_of_trades == 0:
            return 0.0

        negative_trades = [
            trade for trade in trades if trade.net_gain < 0
        ]
        total_number_of_negative_trades = len(negative_trades)
        return total_number_of_negative_trades / total_number_of_trades * 100

    def get_growth_rate_of_backtest(
        self, portfolio_id, tickers, backtest_profile
    ):
        """
        Get the growth rate of the backtest. This function will
        calculate the total value of the portfolio and then
        calculate the growth rate of the portfolio.

        param portfolio_id: The id of the portfolio
        type portfolio_id: str
        param tickers: list of tickers of all the used symbols
        type tickers: dict

        return: The growth rate of the backtest
        """
        total_value = self.get_total_value(
            portfolio_id, tickers, backtest_profile
        )
        gain = total_value - backtest_profile.initial_unallocated
        return gain / backtest_profile.initial_unallocated * 100

    def get_growth_of_backtest(self, portfolio_id, tickers, backtest_profile):
        """
        Get the growth of the backtest. This function will
        calculate the total value of the portfolio and then
        calculate the growth of the portfolio.

        param portfolio_id: The id of the portfolio
        type portfolio_id: str
        param tickers: The tickers of the market
        type tickers: dict

        return: The growth of the backtest
        """
        total_value = self.get_total_value(
            portfolio_id, tickers, backtest_profile
        )
        return total_value - backtest_profile.initial_unallocated

    def get_total_net_gain_percentage_of_backtest(
        self, portfolio_id, backtest_profile
    ):
        """
        Get the total net gain percentage of the backtest. This function
        will calculate the total net gain percentage of the portfolio
        by dividing the total net gain by the initial unallocated value
        of the portfolio and then multiplying it by 100.

        param portfolio_id: The id of the portfolio
        type portfolio_id: str
        param backtest_profile: The backtest profile
        type backtest_profile: BacktestProfile

        return: The total net gain percentage of the backtest
        """
        portfolio = self.portfolio_repository.find({"id": portfolio_id})

        if portfolio.total_net_gain == 0:
            return 0

        return portfolio.total_net_gain \
            / backtest_profile.initial_unallocated * 100

    def get_total_value(self, portfolio_id, tickers, backtest_profile):
        """
        Get the total value of the portfolio. This functions
        will calculate the allocated value, pending buy value,
        pending sell value and unallocated value.

        At the end, it will sum all these values and return the
        total value of the portfolio.

        param portfolio_id: The id of the portfolio
        type portfolio_id: str
        param tickers: The tickers of the market
        type tickers: dict
        param backtest_profile: The backtest profile
        type backtest_profile: BacktestProfile

        return: The total value of the portfolio
        rtype: float
        """
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        positions = self.position_repository.get_all(
            {"portfolio_id": portfolio.id}
        )
        allocated = 0

        for position in positions:

            if position.symbol == portfolio.trading_symbol:
                continue

            ticker_symbol = f"{position.symbol.upper()}" \
                            f"/{portfolio.trading_symbol.upper()}"
            if ticker_symbol not in tickers:
                logger.warning(
                    f"Symbol {position.symbol} not found in tickers, "
                    f"cannot calculate the total value of the position"
                )
                continue

            allocated += position.amount * tickers[ticker_symbol]["bid"]

        # Calculate the pending sell value
        pending_sell_orders = self.order_repository.get_all(
            {
                "portfolio_id": portfolio.id,
                "status": OrderStatus.OPEN.value,
                "order_side": OrderSide.SELL.value,
            }
        )

        for order in pending_sell_orders:

            if order.get_symbol() in tickers:
                allocated += order.get_amount() \
                             * tickers[order.get_symbol()]["bid"]
            else:
                logger.warning(
                    f"Symbol {order.get_symbol()} not found in tickers, "
                    f"cannot calculate the total value of sell orders"
                )

        # Calculate the unallocated value by summing the unallocated and
        # pending buy value
        unallocated = portfolio.unallocated
        pending_buy_orders = self.order_repository.get_all(
            {
                "portfolio_id": portfolio.id,
                "status": OrderStatus.OPEN.value,
                "order_side": OrderSide.BUY.value,
            }
        )

        for order in pending_buy_orders:
            if order.get_symbol() in tickers:
                unallocated += order.get_amount() \
                             * tickers[order.get_symbol()]["ask"]
            else:
                logger.warning(
                    f"Symbol {order.get_symbol()} not found in tickers, "
                    f"cannot calculate the total value of buy orders"
                )

        # Add everything together
        return allocated + unallocated

    def get_average_trade_duration(self, portfolio_id):
        """
        Get the average trade duration. This function will
        calculate the average trade duration by summing the
        duration of all the trades and then dividing it by the
        total number of trades.

        param portfolio_id: The id of the portfolio
        type portfolio_id: str

        return: The average trade duration
        """
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        trades = self.trade_repository.get_all(
            {"portfolio_id": portfolio.id, "status": TradeStatus.CLOSED.value}
        )

        if len(trades) == 0:
            return 0

        total_duration = 0

        for trade in trades:
            duration = trade.closed_at - trade.opened_at
            total_duration += duration.total_seconds() / 3600

        return total_duration / len(trades)

    def get_average_trade_size(self, portfolio_id):
        """
        Get the average trade size. This function will calculate
        the average trade size by summing the size of all the trades
        and then dividing it by the total number of trades.

        param portfolio_id: The id of the portfolio
        type portfolio_id: str

        return: The average trade size
        """
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        trades = self.trade_repository.get_all({"portfolio_id": portfolio.id})

        if len(trades) == 0:
            return 0

        total_size = 0

        for trade in trades:
            total_size += trade.amount * trade.open_price

        return total_size / len(trades)
