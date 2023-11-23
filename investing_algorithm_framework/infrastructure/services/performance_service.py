from investing_algorithm_framework.domain import OrderStatus, OrderSide


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

            allocated += position.amount * tickers[position.symbol]["bid"]

        current_total_value = allocated + portfolio.unallocated
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

            allocated += position.amount * tickers[position.symbol]["bid"]

        current_total_value = allocated + portfolio.unallocated
        return current_total_value - backtest_profile.initial_unallocated

    def get_total_net_gain_percentage_of_backtest(self, portfolio_id, backtest_profile):
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        return portfolio.total_net_gain \
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

            allocated += position.amount * tickers[position.symbol]["bid"]

        return allocated + portfolio.unallocated

    def get_average_trade_duration(self, portfolio_id):
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        buy_orders = self.order_repository.get_all(
            {
                "portfolio_id": portfolio.id,
                "order_side": OrderSide.BUY.value,
            }
        )
        buy_orders_with_trade_closed = [
            order for order in buy_orders if order.get_trade_closed_at() != None
        ]

        if len(buy_orders_with_trade_closed) == 0:
            return 0

        total_duration = 0

        for order in buy_orders_with_trade_closed:
            duration = order.get_trade_closed_at() - order.get_created_at()
            total_duration += duration.total_seconds() / 3600

        return total_duration / len(buy_orders_with_trade_closed)

    def get_average_trade_size(self, portfolio_id):
        portfolio = self.portfolio_repository.find({"id": portfolio_id})
        buy_orders = self.order_repository.get_all(
            {
                "portfolio_id": portfolio.id,
                "order_side": OrderSide.BUY.value,
            }
        )
        closed_buy_orders = [
            order for order in buy_orders
            if order.get_trade_closed_at() != None
        ]

        if len(closed_buy_orders) == 0:
            return 0

        total_size = 0

        for order in closed_buy_orders:
            total_size += order.get_amount() * order.get_price()

        return total_size / len(closed_buy_orders)