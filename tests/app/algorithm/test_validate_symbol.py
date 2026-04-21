from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, OrderSide, DataSource
from investing_algorithm_framework.domain import OperationalException
from tests.resources import TestBase
from tests.resources.strategies_for_testing import StrategyOne


class TestValidateSymbol(TestBase):
    """Tests for opt-in symbol validation on order creation (issue #247)."""
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR"
        )
    ]
    market_credentials = [
        MarketCredential(
            market="BITVAVO",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]
    external_balances = {
        "EUR": 1000
    }

    def _register_data_source(self, symbol):
        """Register a data source symbol in the data provider index."""
        data_source = DataSource(
            identifier=f"{symbol}_ohlcv",
            symbol=symbol,
            data_type="OHLCV",
            time_frame="1d",
            market="BITVAVO",
        )
        data_provider_service = self.app.container.data_provider_service()
        data_provider_service.data_provider_index\
            .data_providers_lookup[data_source] = None

    def test_default_allows_unknown_symbol(self):
        """Default behavior: no symbol validation, any symbol is accepted."""
        self.app.add_strategy(StrategyOne)
        self.app.context.create_limit_order(
            target_symbol="UNKNOWN_TOKEN",
            amount=1,
            price=10,
            order_side=OrderSide.BUY,
        )
        order_repository = self.app.container.order_repository()
        order = order_repository.find({"target_symbol": "UNKNOWN_TOKEN"})
        self.assertIsNotNone(order)

    def test_validate_symbol_false_allows_unknown_symbol(self):
        """Explicit validate_symbol=False allows any symbol."""
        self.app.add_strategy(StrategyOne)
        self.app.context.create_limit_order(
            target_symbol="UNKNOWN_TOKEN",
            amount=1,
            price=10,
            order_side=OrderSide.BUY,
            validate_symbol=False,
        )
        order_repository = self.app.container.order_repository()
        order = order_repository.find({"target_symbol": "UNKNOWN_TOKEN"})
        self.assertIsNotNone(order)

    def test_validate_symbol_true_rejects_unknown_symbol(self):
        """validate_symbol=True raises for a symbol not in data sources."""
        self.app.add_strategy(StrategyOne)
        self._register_data_source("BTC/EUR")

        with self.assertRaises(OperationalException) as cm:
            self.app.context.create_limit_order(
                target_symbol="BT/EUR",
                amount=1,
                price=10,
                order_side=OrderSide.BUY,
                validate_symbol=True,
            )

        self.assertIn("BT/EUR", str(cm.exception))
        self.assertIn("not a known asset", str(cm.exception))
        self.assertIn("BTC/EUR", str(cm.exception))

    def test_validate_symbol_true_accepts_known_symbol(self):
        """validate_symbol=True passes for a symbol in data sources."""
        self.app.add_strategy(StrategyOne)
        self._register_data_source("BTC/EUR")

        self.app.context.create_limit_order(
            target_symbol="BTC/EUR",
            amount=1,
            price=10,
            order_side=OrderSide.BUY,
            validate_symbol=True,
        )
        order_repository = self.app.container.order_repository()
        order = order_repository.find({"target_symbol": "BTC/EUR"})
        self.assertIsNotNone(order)

    def test_validate_symbol_true_multiple_data_sources(self):
        """validate_symbol=True checks across all registered data sources."""
        self.app.add_strategy(StrategyOne)
        self._register_data_source("BTC/EUR")
        self._register_data_source("ETH/EUR")

        # ETH/EUR should pass
        self.app.context.create_limit_order(
            target_symbol="ETH/EUR",
            amount=1,
            price=10,
            order_side=OrderSide.BUY,
            validate_symbol=True,
        )
        order_repository = self.app.container.order_repository()
        order = order_repository.find({"target_symbol": "ETH/EUR"})
        self.assertIsNotNone(order)

        # SOL/EUR should fail
        with self.assertRaises(OperationalException):
            self.app.context.create_limit_order(
                target_symbol="SOL/EUR",
                amount=1,
                price=10,
                order_side=OrderSide.BUY,
                validate_symbol=True,
            )

    def test_validate_symbol_error_message_contains_known_symbols(self):
        """Error message lists known symbols for user reference."""
        self.app.add_strategy(StrategyOne)
        self._register_data_source("BTC/EUR")
        self._register_data_source("ETH/EUR")

        with self.assertRaises(OperationalException) as cm:
            self.app.context.create_limit_order(
                target_symbol="TYPO",
                amount=1,
                price=10,
                order_side=OrderSide.BUY,
                validate_symbol=True,
            )

        error_msg = str(cm.exception)
        self.assertIn("BTC/EUR", error_msg)
        self.assertIn("ETH/EUR", error_msg)
        self.assertIn("validate_symbol=False", error_msg)
