import os
from datetime import datetime
from flask_testing import TestCase
from investing_algorithm_framework.configuration.constants import \
    DATABASE_CONFIG, DATABASE_NAME, RESOURCES_DIRECTORY
from investing_algorithm_framework.core.models import db, OrderStatus
from investing_algorithm_framework import PortfolioManager, MarketService, \
    OrderExecutor, Order, OrderType, OrderSide, AlgorithmContextInitializer
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.app import App
from investing_algorithm_framework.configuration.settings import TestConfig


class Initializer(AlgorithmContextInitializer):
    initialize_has_run = False

    def initialize(self, algorithm) -> None:
        self.initialize_has_run = True


class PortfolioManagerTest(PortfolioManager):
    identifier = "test"
    trading_symbol = "USDT"
    initialize_has_run = False

    def initialize(self, algorithm_context):
        super(PortfolioManagerTest, self).initialize(algorithm_context)
        self.initialize_has_run = True

    def get_initial_unallocated_size(self) -> float:
        return 1000

SYMBOL_A = "SYMBOL_A"
SYMBOL_B = "SYMBOL_B"
SYMBOL_C = "SYMBOL_C"
SYMBOL_D = "SYMBOL_D"

SYMBOL_A_BASE_PRICE = 10
SYMBOL_B_BASE_PRICE = 20
SYMBOL_C_BASE_PRICE = 30
SYMBOL_D_BASE_PRICE = 40

SYMBOL_A_PRICE = 10
SYMBOL_B_PRICE = 20
SYMBOL_C_PRICE = 30
SYMBOL_D_PRICE = 40


def set_symbol_a_price(price):
    global SYMBOL_A_PRICE
    SYMBOL_A_PRICE = price


def set_symbol_b_price(price):
    global SYMBOL_B_PRICE
    SYMBOL_B_PRICE = price


def set_symbol_c_price(price):
    global SYMBOL_C_PRICE
    SYMBOL_C_PRICE = price


def set_symbol_d_price(price):
    global SYMBOL_D_PRICE
    SYMBOL_D_PRICE = price


class OrderExecutorTest(OrderExecutor):
    identifier = "test"

    def execute_limit_order(self, order: Order, algorithm_context, **kwargs):
        portfolio = order.position.portfolio
        market_service = algorithm_context.get_market_service(portfolio.market)

        if not OrderType.LIMIT.equals(order.order_type):
            raise OperationalException(
                "Provided order is not a limit order type"
            )

        if OrderSide.BUY.equals(order.order_side):
            market_service.create_limit_buy_order(
                target_symbol=order.target_symbol,
                trading_symbol=order.trading_symbol,
                amount=order.amount,
                price=order.price
            )
        else:
            market_service.create_limit_sell_order(
                target_symbol=order.target_symbol,
                trading_symbol=order.trading_symbol,
                amount=order.amount,
                price=order.price
            )

    def execute_market_order(self, order: Order, algorithm_context, **kwargs):
        portfolio = order.position.portfolio
        market_service = algorithm_context.get_market_service(portfolio.market)

        if not OrderType.MARKET.equals(order.order_type):
            raise OperationalException(
                "Provided order is not a market order type"
            )

        if OrderSide.BUY.equals(order.order_side):
            market_service.create_market_buy_order(
                target_symbol=order.target_symbol,
                trading_symbol=order.trading_symbol,
                amount=order.amount,
            )
        else:
            market_service.create_market_sell_order(
                target_symbol=order.target_symbol,
                trading_symbol=order.trading_symbol,
                amount=order.amount,
            )

    def get_order_status(self, order: Order, algorithm_context, **kwargs):
        return OrderStatus.SUCCESS.value


class MarketServiceTest(MarketService):
    market = "test"

    def pair_exists(self, target_symbol: str, trading_symbol: str):
        return True

    def get_ticker(self, target_symbol: str, trading_symbol: str):

        if target_symbol == SYMBOL_A:
            return {"price": SYMBOL_A_PRICE, "date": datetime.now()}
        elif target_symbol == SYMBOL_B:
            return {"price": SYMBOL_B_PRICE, "date": datetime.now()}

    def get_order_book(self, target_symbol: str, trading_symbol: str):
        pass

    def get_balance(self, symbol: str = None):
        pass

    def create_limit_buy_order(self, target_symbol: str, trading_symbol: str,
                               amount: float, price: float):
        return True

    def create_limit_sell_order(self, target_symbol: str, trading_symbol: str,
                                amount: float, price: float):
        return True

    def create_market_buy_order(self, target_symbol: str, trading_symbol: str,
                                amount: float):
        return True

    def create_market_sell_order(self, target_symbol: str, trading_symbol: str,
                                 amount: float):
        return True

    def get_orders(self, target_symbol: str, trading_symbol: str):
        pass

    def get_order(self, order_id, target_symbol: str, trading_symbol: str):
        pass

    def get_open_orders(self, target_symbol: str = None,
                        trading_symbol: str = None):
        pass

    def get_closed_orders(self, target_symbol: str = None,
                          trading_symbol: str = None):
        pass

    def cancel_order(self, order_id):
        pass


class TestBase(TestCase):
    resources_dir = os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 'databases'
    )
    algo_app = None

    def create_app(self):
        self.algo_app = App(
            resources_directory=self.resources_dir, config=TestConfig
        )
        self.algo_app._initialize_flask_app()
        self.algo_app._initialize_blueprints()
        return self.algo_app._flask_app

    def setUp(self):
        self.algo_app._configured = False
        self.algo_app._config = TestConfig
        self.algo_app._initialize_config()
        self.algo_app._initialize_database()
        self.algo_app._initialize_flask_config()
        self.algo_app._initialize_flask_sql_alchemy()
        self.algo_app.algorithm.add_initializer(Initializer())
        self.algo_app.algorithm.add_portfolio_manager(PortfolioManagerTest())
        self.algo_app.algorithm.add_market_service(MarketServiceTest())
        self.algo_app.algorithm.add_order_executor(OrderExecutorTest())
        self.algo_app.algorithm.initialize()
        self.algo_app.start_scheduler()
        self.algo_app.algorithm.start()

    def reset_prices(self):
        set_symbol_a_price(SYMBOL_A_BASE_PRICE)
        set_symbol_b_price(SYMBOL_B_BASE_PRICE)
        set_symbol_c_price(SYMBOL_C_BASE_PRICE)
        set_symbol_d_price(SYMBOL_D_BASE_PRICE)

    def tearDown(self) -> None:
        self.reset_prices()
        db.session.remove()
        db.drop_all()

        database_directory_path = self.algo_app.config.get(RESOURCES_DIRECTORY)
        database_name = self.algo_app.config.get(DATABASE_CONFIG)\
            .get(DATABASE_NAME)
        database_path = os.path.join(
            database_directory_path,
            "{}.sqlite3".format(database_name)
        )

        if os.path.isfile(database_path):
            os.remove(database_path)

        self.algo_app.reset()
