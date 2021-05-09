import os
from unittest import TestCase
from investing_algorithm_framework import DataProvider, \
    AbstractPortfolioManager, AbstractOrderExecutor, \
    AlgorithmContextInitializer, AlgorithmContext, Strategy, \
    RelationalDataProvider, ScheduledDataProvider
from investing_algorithm_framework.core.models import Order
from investing_algorithm_framework import TimeUnit


class TestBase(TestCase):
    algorithm_context = None
    data_provider = None
    scheduled_data_provider = None
    relational_data_provider = None
    strategy = None
    portfolio_manager = None
    order_executor = None
    context_initializer = None

    class ContextInitializer(AlgorithmContextInitializer):
        called = 0

        def initialize(self, algorithm_context: AlgorithmContext) -> None:
            self.called += 1

    class PortfolioManager(AbstractPortfolioManager):

        broker = "BINANCE"
        BASE_AMOUNT_USDT = 500

        def get_price(
                self,
                first_symbol: str,
                second_symbol: str,
                algorithm_context: AlgorithmContext
        ) -> float:
            return 20.56

        def get_portfolio_size(
                self, algorithm_context: AlgorithmContext
        ) -> float:
            orders = Order.query.all()
            allocated = 0

            for order in orders:
                allocated += order.total_price

            return self.BASE_AMOUNT_USDT - allocated

        def get_free_portfolio_size(
                self, algorithm_context: AlgorithmContext
        ) -> float:
            orders = Order.query.all()
            allocated = 0

            for order in orders:
                allocated += order.total_price

            return self.BASE_AMOUNT_USDT - allocated

        def get_allocated_portfolio_size(
                self, algorithm_context: AlgorithmContext
        ) -> float:
            pass

        def get_allocated_asset_size(
                self, asset, algorithm_context: AlgorithmContext
        ) -> float:
            pass

    class OrderExecutor(AbstractOrderExecutor):
        broker = "BINANCE"

        def execute_limit_order(
                self,
                to_be_traded_symbol: str,
                traded_against_symbol: str,
                price: float,
                amount: float,
                algorithm_context: AlgorithmContext,
                **kwargs
        ) -> bool:
            pass

        def is_order_executed(self, to_be_traded_symbol: str, traded_against_symbol: str, price: float, amount: float) -> bool:
            return True

    class StandardStrategy(Strategy):
        data_provider_id = None
        called = 0
        on_tick_method_called = False
        on_quote_method_called = False
        on_order_book_method_called = False
        on_raw_data_called = False

        def get_id(self) -> str:
            return self.__class__.__name__

        def on_raw_data(self, data_provider_id, data, algorithm_context):
            self.data_provider_id = data_provider_id
            self.called += 1
            self.on_raw_data_called = True

        def on_order_book(self, data_provider_id, data, algorithm_context):
            self.on_order_book_method_called = True

        def on_quote(self, data_provider_id, data, algorithm_context):
            self.on_quote_method_called = True

        def on_tick(self, data_provider_id, data, algorithm_context):
            self.on_tick_method_called = True

    class StandardDataProvider(DataProvider):
        registered_strategies = []
        cycles = 0

        def extract_tick(self, data, algorithm_context: AlgorithmContext):
            return data

        def extract_quote(self, data, algorithm_context: AlgorithmContext):
            return data

        def extract_order_book(self, data, algorithm_context: AlgorithmContext):
            return data

        def get_data(self, algorithm_context: AlgorithmContext):
            self.cycles += 1
            return "test_data"

    class RelationalDataProvider(RelationalDataProvider):
        registered_strategies = []
        cycles = 0

        def extract_tick(self, data, algorithm_context: AlgorithmContext):
            return data

        def extract_quote(self, data, algorithm_context: AlgorithmContext):
            return data

        def extract_order_book(self, data, algorithm_context: AlgorithmContext):
            return data

        def get_data(self, algorithm_context: AlgorithmContext):
            self.cycles += 1
            return "test_data"

    class ScheduledDataProvider(ScheduledDataProvider):
        time_unit = TimeUnit.SECOND
        time_interval = 2
        cycles = 0

        def get_data(self, algorithm_context: AlgorithmContext):
            self.cycles += 1
            return "test_data"

    def setUp(self) -> None:
        resources_path = os.path.abspath(
            os.path.join(os.path.realpath(__file__), os.pardir)
        )

        self.data_provider = self.StandardDataProvider()
        self.relational_data_provider = self.RelationalDataProvider()
        self.scheduled_data_provider = self.ScheduledDataProvider()
        self.relational_data_provider.run_after = self.data_provider
        self.portfolio_manager = self.PortfolioManager()
        self.order_executor = self.OrderExecutor()
        self.strategy = self.StandardStrategy()
        self.algorithm_context = AlgorithmContext(
            resources_directory=resources_path
        )
        self.context_initializer = self.ContextInitializer()

    def tearDown(self) -> None:
        resources_path = os.path.abspath(
            os.path.join(os.path.realpath(__file__), os.pardir)
        )

        resource_files = os.listdir(resources_path)

        for item in resource_files:
            if item.endswith(".sqlite3") or item.endswith(".sqlite3-journal"):
                os.remove(os.path.join(resources_path, item))

