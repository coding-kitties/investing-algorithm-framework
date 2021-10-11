import os

from investing_algorithm_framework import App, TimeUnit, AlgorithmContext, \
    BinanceOrderExecutor, BinancePortfolioManager

# Make the parent dir your resources directory (database, csv storage)
dir_path = os.path.abspath(os.path.join(os.path.realpath(__file__), os.pardir))

# Create an algorithm application (manages your algorithm, rest api, etc...)
app = App(resources_directory=dir_path)


# Create A portfolio manager connected to your market of
# choice to keep track of your balances
class MyBinancePortfolioManager(BinancePortfolioManager):
    trading_symbol = "USDT"
    api_key = "xxxxx"
    secret_key = "xxxxx"


# Worker that runs every minute to check your pending orders
# (success, failed, canceled)
@app.algorithm.schedule(time_unit=TimeUnit.MINUTE, interval=1)
def check_order_status(context: AlgorithmContext):
    context.check_pending_orders()


# Algorithm strategy that runs every 5 minutes
@app.algorithm.schedule(time_unit=TimeUnit.MINUTE, interval=5)
def perform_strategy(context: AlgorithmContext):
    # Apply strategy ....

    # Execute order
    context.create_market_buy_order(
        "BINANCE", "BTC", amount=10, execute=True
    )


if __name__ == "__main__":
    # Register your market portfolio manager
    app.algorithm.add_portfolio_manager(MyBinancePortfolioManager())

    # Register your market order executor
    app.algorithm.add_order_executor(BinanceOrderExecutor())
    app.start()
