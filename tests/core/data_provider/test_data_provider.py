from tests.resources import TestBase


class TestDataProvider(TestBase):

    def setUp(self) -> None:
        super(TestDataProvider, self).setUp()
        self.data_provider.register_strategy(self.strategy)
        self.algorithm_context.add_data_provider(self.data_provider)

    def test(self) -> None:
        self.algorithm_context.start(1)
        self.assertTrue(self.strategy.on_raw_data_called)
        self.assertTrue(self.strategy.on_tick_method_called)
        self.assertTrue(self.strategy.on_quote_method_called)
        self.assertTrue(self.strategy.on_order_book_method_called)
