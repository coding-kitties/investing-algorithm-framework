import os
from investing_algorithm_framework import App, TimeUnit, Order, \
    AlgorithmContext, PortfolioManager
# from investing_algorithm_framework.configuration import Config


class BinancePortfolioManager(PortfolioManager):
    broker = "BINANCE"
    base_currency = "USDT"

    def get_initial_unallocated_size(self) -> float:
        # Connect to binance and retrieve amount of USDT on account
        pass


app = App(resources_directory=os.path.abspath(os.path.dirname(__file__)))
app.algorithm.add_portfolio_manager(BinancePortfolioManager())


@app.algorithm.schedule(time_unit=TimeUnit.SECONDS, interval=5)
def validate_orders(context: AlgorithmContext):
    portfolio_manager = context.get_portfolio_manager("BINANCE")
    pending_orders = portfolio_manager.get_pending_orders()

    # Check if they are executed
    order_executor = context.get_order_executor("BINANCE")
    order_executor.validate(pending_orders)


@app.algorithm.schedule(time_unit=TimeUnit.SECONDS, interval=5)
def analyze(context: AlgorithmContext):
    portfolio_manager = context.get_portfolio_manager("BINANCE")
    order = portfolio_manager.create_buy_order("BTC", 20, 20)
    portfolio_manager.add_buy_order(order)


if __name__ == '__main__':
    app.start()
