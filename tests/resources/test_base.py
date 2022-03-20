import os
from datetime import datetime
from random import randint
from typing import List

from dateutil.relativedelta import relativedelta
from flask_testing import TestCase

from investing_algorithm_framework import MarketService, \
    OrderExecutor, Order, OrderSide, AlgorithmContextInitializer, \
    DataProvider, OrderBook, Ticker, PortfolioManager, Position
from investing_algorithm_framework.app import App
from investing_algorithm_framework.configuration.constants import \
    DATABASE_CONFIG, DATABASE_NAME, RESOURCES_DIRECTORY
from investing_algorithm_framework.configuration.settings import TestConfig
from investing_algorithm_framework.core.models import db, OrderStatus, \
    SQLLiteAssetPrice
from investing_algorithm_framework.core.portfolio_managers \
    import SQLLitePortfolioManager


class Initializer(AlgorithmContextInitializer):
    initialize_has_run = False

    def initialize(self, algorithm) -> None:
        self.initialize_has_run = True


class PortfolioManagerTest(SQLLitePortfolioManager):
    identifier = "sqlite"
    trading_symbol = "USDT"
    initialize_has_run = False

    def initialize(self, algorithm_context):
        super(PortfolioManagerTest, self).initialize(algorithm_context)
        self.initialize_has_run = True

    def get_prices(
        self, symbols, algorithm_context, **kwargs
    ):
        asset_prices = []

        for symbol in symbols:
            asset_prices.append(TestBase.get_price(symbol))

        return asset_prices

    def get_positions(self, algorithm_context=None, **kwargs) -> List[Position]:
        return [
            Position(
                amount=10000,
                target_symbol=self.get_trading_symbol(algorithm_context)
            )
        ]

    def get_orders(self, algorithm_context, **kwargs) -> List[Order]:
        return []


class DefaultPortfolioManager(PortfolioManager):
    identifier = "default"
    trading_symbol = "USDT"

    def initialize(self, algorithm_context):
        super(DefaultPortfolioManager, self).initialize(algorithm_context)

    def get_prices(
        self, symbols, algorithm_context, **kwargs
    ):
        asset_prices = []

        for symbol in symbols:
            asset_prices.append(TestBase.get_price(symbol))

        return asset_prices

    def get_positions(self, algorithm_context=None, **kwargs) -> List[Position]:
        return [
            Position(
                amount=10000,
                target_symbol=self.get_trading_symbol(algorithm_context)
            )
        ]

    def get_orders(self, algorithm_context, **kwargs) -> List[Order]:
        return []


class OrderExecutorTest(OrderExecutor):
    identifier = "default"

    def execute_order(self, order: Order, algorithm_context,
                      **kwargs) -> Order:
        order.set_reference_id(randint(0, 100))
        return order

    def check_order_status(
        self, order: Order, algorithm_context, **kwargs
    ) -> Order:
        order.set_status(OrderStatus.CLOSED)
        return order


class DataProviderTest(DataProvider):
    market = "test"

    def provide_order_book(
        self, target_symbol, trading_symbol, algorithm_context, **kwargs
    ) -> OrderBook:
        return OrderBook.from_dict(
            {
                "symbol": f"{target_symbol.upper()}{trading_symbol.upper()}",
                "bids": [
                    [37994.54, 1.7179],
                    [37993.52, 0.21408],
                    [37993.51, 0.69057],
                    [37992.01, 0.40006],
                    [37992.0, 1.0],
                    [37990.43, 0.0008],
                    [37988.8, 0.09872],
                    [37988.73, 0.0368],
                    [37988.58, 0.22146],
                    [37988.57, 0.23476],
                    [37988.56, 0.5868],
                    [37988.15, 0.01316],
                    [37987.24, 0.10265],
                    [37987.23, 0.39688],
                    [37987.22, 0.31862],
                    [37987.21, 0.11557],
                    [37987.18, 0.00133],
                    [37987.03, 0.142],
                    [37986.87, 0.0586],
                    [37986.55, 0.00052],
                    [37986.46, 0.05456],
                    [37986.29, 0.23999],
                    [37986.28, 0.14999],
                    [37986.06, 0.15],
                    [37985.97, 0.31666],
                    [37985.96, 0.025],
                    [37985.95, 0.355],
                    [37985.31, 0.00133],
                    [37985.25, 0.20833],
                    [37985.11, 0.06577],
                    [37984.96, 0.09212],
                    [37984.61, 0.18221],
                    [37984.05, 0.16],
                    [37984.01, 0.00035],
                    [37983.44, 0.00133],
                    [37983.08, 0.10266],
                    [37982.81, 0.17104],
                    [37982.8, 0.71987],
                    [37982.79, 0.13155],
                    [37982.62, 0.15],
                    [37982.19, 0.747],
                    [37981.85, 1.60446],
                    [37981.84, 1.9],
                    [37981.83, 0.1685],
                    [37981.57, 0.00133], [37981.36, 0.2], [37980.75, 0.09213], [37980.13, 0.1], [37980.12, 0.15093], [37979.7, 0.00133], [37979.34, 0.21341], [37979.33, 0.18842], [37979.32, 0.13154], [37978.12, 0.05], [37978.1, 0.143], [37977.83, 0.00133], [37977.45, 1.62834], [37977.44, 0.02063], [37977.19, 2.30552], [37976.3, 0.3004], [37976.26, 0.53158], [37976.25, 0.40925], [37976.08, 0.152], [37975.96, 0.00133], [37975.73, 0.26725], [37975.2, 0.19732], [37975.09, 0.00263], [37974.53, 0.04221], [37974.26, 0.00288], [37974.09, 0.00133], [37974.05, 0.14254], [37974.01, 0.1], [37973.79, 1.17033], [37973.75, 0.881], [37973.71, 0.26323], [37973.41, 0.26725], [37973.06, 0.18865], [37972.58, 0.05325], [37972.5, 0.03972], [37972.22, 0.00133], [37972.13, 0.05345], [37972.12, 0.00263], [37972.11, 0.34424], [37972.03, 0.001], [37972.02, 0.15165], [37971.97, 0.03585], [37971.82, 0.02927], [37971.14, 0.09215], [37971.11, 0.00036], [37971.02, 0.14698], [37970.35, 0.00133], [37970.01, 0.00344], [37970.0, 0.05251], [37969.98, 0.15099], [37969.69, 0.15], [37968.99, 0.01], [37968.76, 0.01], [37968.71, 0.44813], [37968.48, 0.00133], [37968.41, 0.07782]],
                "asks": [[37994.55, 0.18691], [37994.57, 0.01316], [37994.89, 0.00052], [37996.39, 0.00081], [37996.51, 0.0253], [37996.62, 0.01205], [37996.96, 0.13156], [37997.0, 0.09], [37997.92, 0.13154], [37998.62, 0.00031], [37999.89, 0.143], [38000.0, 0.09299], [38000.27, 0.00133], [38000.3, 0.05683], [38000.31, 0.142], [38002.14, 0.13293], [38002.5, 0.001], [38003.29, 0.19209], [38003.3, 0.26929], [38003.31, 0.19732], [38003.95, 0.0121], [38004.01, 0.00133], [38004.09, 0.63278], [38004.1, 0.26323], [38004.11, 0.749], [38004.55, 0.05], [38004.83, 0.242], [38005.87, 0.165], [38005.88, 0.00133], [38006.28, 0.00615], [38007.0, 0.00036], [38007.15, 0.06191], [38007.16, 0.9349], [38007.17, 0.02491], [38007.2, 0.881], [38007.29, 0.15073], [38007.51, 0.19714], [38007.53, 0.19956], [38007.72, 0.00674], [38007.75, 0.00133], [38008.85, 0.82575], [38008.87, 0.20609], [38008.89, 0.2], [38009.05, 0.21677], [38009.17, 0.2], [38009.23, 0.18926], [38009.31, 0.14506], [38009.49, 0.10135], [38009.57, 0.142], [38009.62, 0.00133], [38009.67, 0.1], [38009.87, 0.0039], [38009.99, 0.001], [38010.0, 0.00265], [38010.52, 0.00055], [38010.61, 1.80645], [38010.62, 0.2], [38010.65, 0.03314], [38011.0, 0.00498], [38011.27, 2.19641], [38011.32, 0.14599], [38011.4, 0.05096], [38011.49, 0.00133], [38012.0, 0.03056], [38012.11, 0.00232], [38012.42, 0.18239], [38012.65, 0.06475], [38013.36, 0.00133], [38013.37, 0.14544], [38013.77, 0.00347], [38014.59, 0.00999], [38014.77, 0.10949], [38014.89, 0.05], [38015.03, 0.06592], [38015.11, 0.10942], [38015.23, 0.00133], [38015.41, 0.14752], [38016.04, 0.66], [38016.46, 0.14409], [38017.1, 0.00133], [38017.45, 0.1476], [38017.5, 0.03314], [38018.56, 0.02043], [38018.97, 0.00133], [38019.0, 0.07391], [38020.16, 0.14679], [38020.17, 0.54877], [38020.29, 0.14662], [38020.84, 0.00133], [38021.0, 0.00249], [38021.06, 0.13495], [38021.89, 0.05853], [38022.38, 0.24808], [38022.71, 0.00133], [38022.78, 0.21811], [38022.79, 0.16478], [38023.0, 0.00396], [38023.06, 0.04021], [38023.18, 0.14546], [38023.52, 0.00039]],
                "creation_date": "2022-02-04 13:33:48.945664"
            }
        )

    def provide_ticker(
        self, target_symbol, trading_symbol, algorithm_context, **kwargs
    ) -> Ticker:

        return Ticker.from_dict(
            {
                "symbol": f"{target_symbol.upper()}{trading_symbol.upper()}",
                "price": TestBase.get_price(target_symbol),
                "ask_price": TestBase.get_price(target_symbol),
                "ask_volume": 1,
                "bid_price": TestBase.get_price(target_symbol),
                "bid_volume": 1,
                "high_price": TestBase.get_price(target_symbol),
                "low_price": TestBase.get_price(target_symbol),
                "creation_date": "2022-02-04 13:33:48.945664"
            }
        )

    def provide_raw_data(self, algorithm_context, **kwargs) -> dict:
        return {"message": "hello"}


class MarketServiceTest(MarketService):
    market = "test"

    def pair_exists(self, target_symbol: str, trading_symbol: str):
        return True

    def get_ticker(self, symbol):
        return TestBase.get_price(
            symbol=symbol, date=datetime.utcnow()
        )

    def get_tickers(self, symbols):
        return []

    def get_prices(self, symbols):

        asset_prices = []

        for symbol in symbols:
            asset_prices.append(
                TestBase.get_price(symbol=symbol, date=datetime.utcnow())
            )

        return asset_prices

    def get_order_book(self, symbol):
        pass

    def get_balance(self, symbol: str = None):
        pass

    def get_balances(self):
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

    def get_orders(self):
        pass

    def get_order(self, order_id):
        pass

    def get_open_orders(self, target_symbol: str = None,
                        trading_symbol: str = None):
        pass

    def get_closed_orders(self, target_symbol: str = None,
                          trading_symbol: str = None):
        pass

    def cancel_order(self, order_id):
        pass

    def get_ohclv(self, symbol, time_unit, since):
        pass

    def get_ohclvs(self, symbols, time_unit, since):
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
        self.algo_app.initialize(resources_directory="/tmp", config=TestConfig)
        self.algo_app._initialize_config()
        self.algo_app._initialize_database()
        self.algo_app._initialize_flask_config()
        self.algo_app._initialize_flask_sql_alchemy()
        self.algo_app.algorithm.add_initializer(Initializer())
        self.algo_app.algorithm.add_portfolio_manager(PortfolioManagerTest())
        self.algo_app.algorithm.add_portfolio_manager(DefaultPortfolioManager)
        self.algo_app.algorithm.add_market_service(MarketServiceTest())
        self.algo_app.algorithm.add_order_executor(OrderExecutorTest())
        self.algo_app.algorithm.add_data_provider(DataProviderTest)
        self.algo_app.start_scheduler()

        TestBase.prices_symbol_a = [
            SQLLiteAssetPrice(
                symbol=f"{self.TARGET_SYMBOL_A}/USDT",
                price=self.BASE_SYMBOL_A_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15)
            )
        ]
        TestBase.prices_symbol_b = [
            SQLLiteAssetPrice(
                symbol=f"{self.TARGET_SYMBOL_B}/USDT",
                price=self.BASE_SYMBOL_B_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15)
            )
        ]
        TestBase.prices_symbol_c = [
            SQLLiteAssetPrice(
                symbol=f"{self.TARGET_SYMBOL_C}/USDT",
                price=self.BASE_SYMBOL_C_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15)
            )
        ]
        TestBase.prices_symbol_d = [
            SQLLiteAssetPrice(
                symbol=f"{self.TARGET_SYMBOL_D}/USDT",
                price=self.BASE_SYMBOL_D_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15)
            )
        ]
        TestBase.prices_symbol_e = [
            SQLLiteAssetPrice(
                symbol=f"{self.TARGET_SYMBOL_E}/USDT",
                price=self.BASE_SYMBOL_E_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15)
            )
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
    def get_price(symbol, date=datetime.now()):

        if symbol.split("/")[0] == "USDT":
            return SQLLiteAssetPrice(
                price=1,
                datetime=datetime.utcnow(),
                symbol="USDT"
            )

        target_symbol = symbol.split("/")[0]

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

        if order.get_trading_symbol() is None:
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

        if not OrderStatus.PENDING.equals(order.status) \
                and not OrderStatus.TO_BE_SENT.equals(order.status) \
                and order.initial_price is None:
            msg = "Initial price is not set"
            raise self.failureException(msg)

        if executed:

            if order.status is None:
                msg = "Order status is None"
                raise self.failureException(msg)

            if order.status is OrderStatus.CLOSED.value:
                msg = "Order status is not closed"
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

        if OrderSide.SELL.equals(order.side):
            if order.amount_target_symbol is None:
                msg = "Amount trading symbol is not set"
                raise self.failureException(msg)

        if executed:
            if order.amount_target_symbol <= 0:
                msg = "Amount is too small"
                raise self.failureException(msg)

            if order.get_price() <= 0:
                msg = "Price is too small"
                raise self.failureException(msg)

            if order.status is None:
                msg = "Order status is None"
                raise self.failureException(msg)

            if order.status is OrderStatus.CLOSED.value:
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

        TestBase.prices_symbol_a = [
            SQLLiteAssetPrice(
                symbol=f"{TestBase.TARGET_SYMBOL_A}/USDT",
                price=TestBase.BASE_SYMBOL_A_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15)
            )
        ]
        TestBase.prices_symbol_b = [
            SQLLiteAssetPrice(
                symbol=f"{TestBase.TARGET_SYMBOL_B}/USDT",
                price=TestBase.BASE_SYMBOL_B_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15))
        ]
        TestBase.prices_symbol_c = [
            SQLLiteAssetPrice(
                symbol=f"{TestBase.TARGET_SYMBOL_C}/USDT",
                price=TestBase.BASE_SYMBOL_C_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15)
            )
        ]
        TestBase.prices_symbol_d = [
            SQLLiteAssetPrice(
                symbol=f"{TestBase.TARGET_SYMBOL_D}/USDT",
                price=TestBase.BASE_SYMBOL_D_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15)
            )
        ]
        TestBase.prices_symbol_e = [
            SQLLiteAssetPrice(
                symbol=f"{TestBase.TARGET_SYMBOL_E}/USDT",
                price=TestBase.BASE_SYMBOL_E_PRICE,
                datetime=datetime.utcnow() - relativedelta(years=15)
            )
        ]
