from investing_algorithm_framework.domain import OrderStatus, OrderSide, \
    parse_string_to_decimal
from decimal import Decimal


class PerformanceService:

    def __init__(
        self,
        order_repository,
        position_repository,
        portfolio_repository,
    ):
        self.order_repository = order_repository
        self.position_repository = position_repository
        self.portfolio_repository = portfolio_repository

    def get_total_net_gain(self, portfolio_id):
        pass

    def get_total_size(self, portfolio_id):
        pass

    def get_percentage_change(self, portfolio_id, time_frame):
        pass

    def get_total_cost(self, portfolio_id):
        pass

    def get_number_of_trades_closed(self, portfolio_id):
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        number_of_trades_closed = 0
        orders = self.order_repository.get_all(
            {
                "portfolio_id": portfolio.id,
                "order_side": OrderSide.BUY.value,
            }
        )

        for order in orders:
            if order.get_trade_closed_at() is not None:
                number_of_trades_closed += 1

        return number_of_trades_closed

    def get_number_of_trades_open(self, portfolio_id):
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        number_of_trades_open = 0
        orders = self.order_repository.get_all(
            {
                "portfolio_id": portfolio.id,
                "order_side": OrderSide.BUY.value,
            }
        )

        for order in orders:
            if order.get_trade_closed_at() is None:
                number_of_trades_open += 1

        return number_of_trades_open

    def get_percentage_positive_trades(self, portfolio_id):
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        orders = self.order_repository.get_all(
            {"portfolio_id": portfolio.id, "status": OrderStatus.CLOSED.value}
        )
        total_number_of_orders = len(orders)

        if total_number_of_orders == 0:
            return 0.0

        positive_orders = [
            order for order in orders if order.get_net_gain() > 0
        ]
        total_number_of_positive_orders = len(positive_orders)
        return total_number_of_positive_orders / total_number_of_orders * 100

    def get_percentage_negative_trades(self, portfolio_id):
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        orders = self.order_repository.get_all(
            {"portfolio_id": portfolio.id, "status": OrderStatus.CLOSED.value}
        )
        total_number_of_orders = len(orders)

        if total_number_of_orders == 0:
            return 0.0

        negative_orders = [
            order for order in orders if order.get_net_gain() < 0
        ]
        total_number_of_negative_orders = len(negative_orders)
        return total_number_of_negative_orders / total_number_of_orders * 100

    def get_growth_rate_of_backtest(self, portfolio_id, tickers, backtest_profile):
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        positions = self.position_repository.get_all(
            {"portfolio_id": portfolio.id}
        )
        allocated = 0

        for position in positions:

            if position.symbol == portfolio.trading_symbol:
                continue

            allocated += parse_string_to_decimal(position.amount)\
                * Decimal(tickers[position.symbol]["bid"])

        current_total_value = allocated + \
            parse_string_to_decimal(portfolio.unallocated)
        gain = current_total_value - backtest_profile.initial_unallocated
        return gain / backtest_profile.initial_unallocated * 100

    def get_growth_of_backtest(self, portfolio_id, tickers, backtest_profile):
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        positions = self.position_repository.get_all(
            {"portfolio_id": portfolio.id}
        )
        allocated = 0

        for position in positions:

            if position.symbol == portfolio.trading_symbol:
                continue

            allocated += parse_string_to_decimal(position.amount)\
                * Decimal(tickers[position.symbol]["bid"])

        current_total_value = allocated + \
            parse_string_to_decimal(portfolio.unallocated)
        return current_total_value - backtest_profile.initial_unallocated

    def get_total_net_gain_percentage_of_backtest(self, portfolio_id, backtest_profile):
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        return parse_string_to_decimal(portfolio.total_net_gain) \
               / backtest_profile.initial_unallocated * 100

    def get_total_value(self, portfolio_id, tickers, backtest_profile):
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        positions = self.position_repository.get_all(
            {"portfolio_id": portfolio.id}
        )
        allocated = 0

        for position in positions:

            if position.symbol == portfolio.trading_symbol:
                continue

            allocated += parse_string_to_decimal(position.amount)\
                * Decimal(tickers[position.symbol]["bid"])

        return allocated + parse_string_to_decimal(portfolio.unallocated)
