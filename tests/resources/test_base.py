import os
from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from flask_testing import TestCase

from investing_algorithm_framework import MarketService, \
    OrderExecutor, Order, OrderType, OrderSide, AlgorithmContextInitializer
from investing_algorithm_framework.app import App
from investing_algorithm_framework.configuration.constants import \
    DATABASE_CONFIG, DATABASE_NAME, RESOURCES_DIRECTORY
from investing_algorithm_framework.configuration.settings import TestConfig
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import db, OrderStatus, \
    TimeInterval, SQLLiteAssetPrice, SQLLiteAssetPriceHistory
from investing_algorithm_framework.core.portfolio_managers \
    import SQLLitePortfolioManager


class Initializer(AlgorithmContextInitializer):
    initialize_has_run = False

    def initialize(self, algorithm) -> None:
        self.initialize_has_run = True


class PortfolioManagerTest(SQLLitePortfolioManager):

    def get_unallocated_synced(self, algorithm_context):
        return 1000

    def get_positions_synced(self, algorithm_context):
        pass

    market = "test"
    identifier = "test"
    trading_symbol = "USDT"
    initialize_has_run = False

    def initialize(self, algorithm_context):
        super(PortfolioManagerTest, self).initialize(algorithm_context)
        self.initialize_has_run = True


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
                price=order.initial_price
            )
        else:
            market_service.create_limit_sell_order(
                target_symbol=order.target_symbol,
                trading_symbol=order.trading_symbol,
                amount=order.amount,
                price=order.initial_price
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
        return TestBase.get_price(
            target_symbol=target_symbol, date=datetime.utcnow()
        )

    def get_prices(
        self,
        target_symbol: str,
        trading_symbol: str,
        time_interval: TimeInterval
    ):
        from investing_algorithm_framework.core.models.snapshots \
            import AssetPrice
        asset_prices = []

        for i in range(0, time_interval.amount_of_data_points()):

            if TimeInterval.MINUTES_ONE.equals(time_interval):
                date = datetime.utcnow() - timedelta(minutes=i)

            if TimeInterval.MINUTES_FIFTEEN.equals(time_interval):
                date = datetime.utcnow() - timedelta(minutes=i * 15)

            if TimeInterval.HOURS_ONE.equals(time_interval):
                date = datetime.utcnow() - timedelta(hours=i)

            if TimeInterval.HOURS_FOUR.equals(time_interval):
                date = datetime.utcnow() - timedelta(hours=i * 4)

            if TimeInterval.DAYS_ONE.equals(time_interval):
                date = datetime.utcnow() - timedelta(days=i)

            asset_price = TestBase.get_price(target_symbol, date)
            asset_prices.insert(
                0,
                SQLLiteAssetPrice(
                    target_symbol=target_symbol,
                    trading_symbol=trading_symbol,
                    price=asset_price.price,
                    datetime=date
                )
            )

        return asset_prices

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
    TRADING_SYMBOL = "USDT"
    TARGET_SYMBOL_A = "SYMBOL_A"
    TARGET_SYMBOL_B = "SYMBOL_B"
    TARGET_SYMBOL_C = "SYMBOL_C"
    TARGET_SYMBOL_D = "SYMBOL_D"
    TARGET_SYMBOL_E = "SYMBOL_E"
    BASE_SYMBOL_A_PRICE = 50
    BASE_SYMBOL_B_PRICE = 20
    BASE_SYMBOL_C_PRICE = 10
    BASE_SYMBOL_D_PRICE = 80
    BASE_SYMBOL_E_PRICE = 90

    prices_symbol_a = []
    prices_symbol_b = []
    prices_symbol_c = []
    prices_symbol_d = []
    prices_symbol_e = []

    def create_app(self):
        self.algo_app = App(
            resources_directory=self.resources_dir, config=TestConfig
        )
        self.algo_app._initialize_flask_app()
        self.algo_app._initialize_blueprints()
        return self.algo_app._flask_app

    def start_algorithm(self):
        self.algo_app.algorithm.start()

    def setUp(self):
        self.algo_app.reset()
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

        from investing_algorithm_framework.core.models.snapshots import \
            AssetPrice

        TestBase.prices_symbol_a = [
            SQLLiteAssetPrice(target_symbol=self.TARGET_SYMBOL_A, trading_symbol="usdt",
                       price=self.BASE_SYMBOL_A_PRICE,
                       datetime=datetime.utcnow() - relativedelta(years=15))
        ]
        TestBase.prices_symbol_b = [
            SQLLiteAssetPrice(target_symbol=self.TARGET_SYMBOL_B, trading_symbol="usdt",
                       price=self.BASE_SYMBOL_B_PRICE,
                       datetime=datetime.utcnow() - relativedelta(years=15))
        ]
        TestBase.prices_symbol_c = [
            SQLLiteAssetPrice(target_symbol=self.TARGET_SYMBOL_C, trading_symbol="usdt",
                       price=self.BASE_SYMBOL_C_PRICE,
                       datetime=datetime.utcnow() - relativedelta(years=15))
        ]
        TestBase.prices_symbol_d = [
            SQLLiteAssetPrice(target_symbol=self.TARGET_SYMBOL_D, trading_symbol="usdt",
                       price=self.BASE_SYMBOL_D_PRICE,
                       datetime=datetime.utcnow() - relativedelta(years=15))
        ]
        TestBase.prices_symbol_e = [
            SQLLiteAssetPrice(target_symbol=self.TARGET_SYMBOL_E, trading_symbol="usdt",
                       price=self.BASE_SYMBOL_E_PRICE,
                       datetime=datetime.utcnow() - relativedelta(years=15))
        ]

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

    def assert_almost_equal(self, first, second, max_difference):
        if not abs(first - second) < max_difference:
            msg = f"Difference between {first} and {second} is larger " \
                  f"then {max_difference}"
            raise self.failureException(msg)

    @staticmethod
    def get_price(target_symbol, date=datetime.now()):

        if target_symbol == TestBase.TARGET_SYMBOL_A:
            prices = TestBase.prices_symbol_a

        if target_symbol == TestBase.TARGET_SYMBOL_B:
            prices = TestBase.prices_symbol_b

        if target_symbol == TestBase.TARGET_SYMBOL_C:
            prices = TestBase.prices_symbol_c

        if target_symbol == TestBase.TARGET_SYMBOL_D:
            prices = TestBase.prices_symbol_d

        if target_symbol == TestBase.TARGET_SYMBOL_E:
            prices = TestBase.prices_symbol_e

        return TestBase._get_price(prices, date)

    def update_price(self, target_symbol, price, date=datetime.utcnow()):
        from investing_algorithm_framework.core.models.snapshots \
            import AssetPrice

        if target_symbol == TestBase.TARGET_SYMBOL_A:
            prices = TestBase.prices_symbol_a
            TestBase.prices_symbol_a = TestBase._append_price(
                prices,
                SQLLiteAssetPrice(
                    target_symbol=target_symbol,
                    trading_symbol="USDT",
                    price=price,
                    datetime=date
                )
            )
        if target_symbol == TestBase.TARGET_SYMBOL_B:
            prices = TestBase.prices_symbol_b
            TestBase.prices_symbol_b = TestBase._append_price(
                prices,
                SQLLiteAssetPrice(
                    target_symbol=target_symbol,
                    trading_symbol="USDT",
                    price=price,
                    datetime=date
                )
            )

        if target_symbol == TestBase.TARGET_SYMBOL_C:
            prices = TestBase.prices_symbol_c
            TestBase.prices_symbol_c = TestBase._append_price(
                prices,
                SQLLiteAssetPrice(
                    target_symbol=target_symbol,
                    trading_symbol="USDT",
                    price=price,
                    datetime=date
                )
            )

        if target_symbol == TestBase.TARGET_SYMBOL_D:
            prices = TestBase.prices_symbol_d
            TestBase.prices_symbol_d = TestBase._append_price(
                prices,
                SQLLiteAssetPrice(
                    target_symbol=target_symbol,
                    trading_symbol="USDT",
                    price=price,
                    datetime=date
                )
            )

        if target_symbol == TestBase.TARGET_SYMBOL_E:
            prices = TestBase.prices_symbol_e
            TestBase.prices_symbol_e = TestBase._append_price(
                prices,
                SQLLiteAssetPrice(
                    target_symbol=target_symbol,
                    trading_symbol="USDT",
                    price=price,
                    datetime=date
                )
            )

    @property
    def tickers(self):
        return [
            self.TARGET_SYMBOL_A,
            self.TARGET_SYMBOL_B,
            self.TARGET_SYMBOL_C,
            self.TARGET_SYMBOL_D,
            self.TARGET_SYMBOL_E
        ]

    def assert_is_limit_order(self, order, executed = False):

        if order.trading_symbol is None:
            msg = "Trading symbol is not set"
            raise self.failureException(msg)

        if order.target_symbol is None:
            msg = "Target symbol is not set"
            raise self.failureException(msg)

        if order.trading_symbol == order.target_symbol:
            msg = "Target symbol and trading symbol are the same"
            raise self.failureException(msg)

        if order.amount_target_symbol is None:
            msg = "Amount target symbol is not set"
            raise self.failureException(msg)

        if order.amount_target_symbol <= 0:
            msg = "Amount target symbol is too small"
            raise self.failureException(msg)

        if order.amount_trading_symbol is None:
            msg = "Amount trading symbol is not set"
            raise self.failureException(msg)

        if order.amount_trading_symbol <= 0:
            msg = "Amount trading symbol is too small"
            raise self.failureException(msg)

        if order.initial_price <= 0:
            msg = "Price is too small"
            raise self.failureException(msg)

        if executed:
            if order.position is None:
                msg = "Position is not set"
                raise self.failureException(msg)

            if order.status is None:
                msg = "Order status is None"
                raise self.failureException(msg)

            if order.status is OrderStatus.SUCCESS.value:
                msg = "Order status is not value SUCCESS"
                raise self.failureException(msg)

    def assert_is_market_order(self, order, executed = False):

        if order.trading_symbol is None:
            msg = "Trading symbol is not set"
            raise self.failureException(msg)

        if order.target_symbol is None:
            msg = "Target symbol is not set"
            raise self.failureException(msg)

        if order.trading_symbol == order.target_symbol:
            msg = "Target symbol and trading symbol are the same"
            raise self.failureException(msg)

        if OrderSide.SELL.equals(order.order_side):
            if order.amount_target_symbol is None:
                msg = "Amount trading symbol is not set"
                raise self.failureException(msg)

        if executed:
            if order.amount_target_symbol <= 0:
                msg = "Amount is too small"
                raise self.failureException(msg)

            if order.price <= 0:
                msg = "Price is too small"
                raise self.failureException(msg)

            if order.position is None:
                msg = "Position is not set"
                raise self.failureException(msg)

            if order.status is None:
                msg = "Order status is None"
                raise self.failureException(msg)

            if order.status is OrderStatus.SUCCESS.value:
                msg = "Order status is not value SUCCESS"
                raise self.failureException(msg)

    def assert_is_portfolio_snapshot(self, snapshot):

        if snapshot.id is None:
            msg = "Snapshot has no id"
            raise self.failureException(msg)

        if snapshot.created_at is None:
            msg = "Snapshot has no created at set"
            raise self.failureException(msg)

        if snapshot.portfolio_id is None:
            msg = "Snapshot has no portfolio id set"
            raise self.failureException(msg)

        if snapshot.portfolio_id is None:
            msg = "Snapshot has no portfolio id set"
            raise self.failureException(msg)

        if snapshot.market is None:
            msg = "Snapshot market is not set"
            raise self.failureException(msg)

        if snapshot.trading_symbol is None:
            msg = "Snapshot trading symbol is not set"
            raise self.failureException(msg)

        if snapshot.realized is None:
            msg = "Snapshot realized is not set"
            raise self.failureException(msg)

        if snapshot.unallocated is None:
            msg = "Snapshot unallocated is not set"
            raise self.failureException(msg)

        if snapshot.total_revenue is None:
            msg = "Snapshot total_revenue is not set"
            raise self.failureException(msg)

        if snapshot.created_at is None:
            msg = "Snapshot created_at is not set"
            raise self.failureException(msg)

    def assert_is_position_snapshot(self, snapshot):
        pass

    @staticmethod
    def _append_price(prices, asset_price):
        previous_index = 0
        current_index = 0
        appended = False

        for price in prices:

            if current_index != 0:
                previous_index = current_index

            current = price
            current_index += 1

            if current.datetime > asset_price.datetime:
                prices = prices.insert(previous_index, asset_price)
                appended = True
                break

        if not appended:
            prices.append(asset_price)

        return prices

    @staticmethod
    def _get_price(prices, target_date):

        if len(prices) == 1:
            return prices[0]

        current_price = None

        for price in prices:
            previous_price = current_price
            current_price = price

            # In the future
            if current_price.datetime >= target_date:

                if current_price.datetime == target_date:
                    return current_price

                return previous_price

        return prices[-1]

    def reset_prices(self):

        from investing_algorithm_framework.core.models.snapshots \
            import AssetPrice

        TestBase.prices_symbol_a = [
            SQLLiteAssetPrice(
                target_symbol=TestBase.TARGET_SYMBOL_A,
                trading_symbol="USDT",
                price=TestBase.BASE_SYMBOL_A_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15)
            )
        ]
        TestBase.prices_symbol_b = [
            SQLLiteAssetPrice(
                target_symbol=TestBase.TARGET_SYMBOL_B,
                trading_symbol="USDT",
                price=TestBase.BASE_SYMBOL_B_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15))
        ]
        TestBase.prices_symbol_c = [
            SQLLiteAssetPrice(
                target_symbol=TestBase.TARGET_SYMBOL_C,
                trading_symbol="USDT",
                price=TestBase.BASE_SYMBOL_C_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15)
            )
        ]
        TestBase.prices_symbol_d = [
            SQLLiteAssetPrice(
                target_symbol=TestBase.TARGET_SYMBOL_D,
                trading_symbol="TestBase",
                price=TestBase.BASE_SYMBOL_D_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15)
            )
        ]
        TestBase.prices_symbol_e = [
            SQLLiteAssetPrice(
                target_symbol=TestBase.TARGET_SYMBOL_E,
                trading_symbol="USDT",
                price=TestBase.BASE_SYMBOL_E_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15)
            )
        ]

    def create_limit_order(
        self,
        portfolio,
        target_symbol,
        amount,
        price,
        creation_datetime=datetime.utcnow(),
        side=OrderSide.BUY.value,
        execution_datetime=None,
        executed=True,
    ):
        order = portfolio.create_order(
            self.algo_app.algorithm,
            order_side=side,
            order_type=OrderType.LIMIT.value,
            symbol=target_symbol,
            amount_target_symbol=amount,
            price=price,
        )

        order.created_at = creation_datetime
        portfolio.add_order(order)

        if not execution_datetime:
            # Order is a minute later executed
            executed_at = creation_datetime + timedelta(minutes=4)
        else:
            executed_at = execution_datetime

        if executed:
            order.set_pending()
            order.set_executed(snapshot=True, executed_at=executed_at)

        return order
