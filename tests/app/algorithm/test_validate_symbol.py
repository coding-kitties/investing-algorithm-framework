from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, OrderSide, OrderType, DataSource
from investing_algorithm_framework.domain import OperationalException
from tests.resources import TestBase
from tests.resources.strategies_for_testing import StrategyOne


class TestValidateSymbol(TestBase):
    """Tests for opt-in symbol validation on order creation (issue #247).

    Validates:
    1. target_symbol is not the same as trading_symbol (e.g. EUR/EUR)
    2. A data source exists for the target_symbol/trading_symbol pair
    """
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

    def test_default_allows_any_symbol(self):
        """Default behavior: no validation, any symbol is accepted."""
        self.app.add_strategy(StrategyOne)
        self.app.context.create_limit_order(
            target_symbol="EUR",
            amount=1,
            price=10,
            order_side=OrderSide.BUY,
        )
        order_repository = self.app.container.order_repository()
        order = order_repository.find({"target_symbol": "EUR"})
        self.assertIsNotNone(order)

    def test_validate_symbol_false_allows_any_symbol(self):
        """Explicit validate_symbol=False skips all validation."""
        self.app.add_strategy(StrategyOne)
        self.app.context.create_limit_order(
            target_symbol="EUR",
            amount=1,
            price=10,
            order_side=OrderSide.BUY,
            validate_symbol=False,
        )
        order_repository = self.app.container.order_repository()
        order = order_repository.find({"target_symbol": "EUR"})
        self.assertIsNotNone(order)

    def test_rejects_target_equals_trading_symbol(self):
        """Rejects orders where target_symbol == trading_symbol (EUR/EUR)."""
        self.app.add_strategy(StrategyOne)

        with self.assertRaises(OperationalException) as cm:
            self.app.context.create_limit_order(
                target_symbol="EUR",
                amount=1,
                price=10,
                order_side=OrderSide.BUY,
                validate_symbol=True,
            )

        error_msg = str(cm.exception)
        self.assertIn("EUR/EUR", error_msg)
        self.assertIn("trading_symbol", error_msg)

    def test_rejects_target_equals_trading_symbol_case_insensitive(self):
        """Case-insensitive check for target == trading_symbol."""
        self.app.add_strategy(StrategyOne)

        with self.assertRaises(OperationalException):
            self.app.context.create_limit_order(
                target_symbol="eur",
                amount=1,
                price=10,
                order_side=OrderSide.BUY,
                validate_symbol=True,
            )

    def test_rejects_missing_data_source(self):
        """Rejects when no data source is registered for the pair."""
        self.app.add_strategy(StrategyOne)

        with self.assertRaises(OperationalException) as cm:
            self.app.context.create_limit_order(
                target_symbol="BTC",
                amount=1,
                price=10,
                order_side=OrderSide.BUY,
                validate_symbol=True,
            )

        error_msg = str(cm.exception)
        self.assertIn("BTC/EUR", error_msg)
        self.assertIn("No data source registered", error_msg)

    def test_accepts_with_matching_data_source(self):
        """Passes when a data source exists for target/trading pair."""
        self.app.add_strategy(StrategyOne)
        self._register_data_source("BTC/EUR")

        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side=OrderSide.BUY,
            validate_symbol=True,
        )
        order_repository = self.app.container.order_repository()
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertIsNotNone(order)

    def test_rejects_wrong_data_source(self):
        """Rejects when only a different pair is registered."""
        self.app.add_strategy(StrategyOne)
        self._register_data_source("ETH/EUR")

        with self.assertRaises(OperationalException) as cm:
            self.app.context.create_limit_order(
                target_symbol="BTC",
                amount=1,
                price=10,
                order_side=OrderSide.BUY,
                validate_symbol=True,
            )

        error_msg = str(cm.exception)
        self.assertIn("BTC/EUR", error_msg)
        self.assertIn("ETH/EUR", error_msg)

    def test_error_message_lists_registered_symbols(self):
        """Error message includes registered data source symbols."""
        self.app.add_strategy(StrategyOne)
        self._register_data_source("BTC/EUR")
        self._register_data_source("ETH/EUR")

        with self.assertRaises(OperationalException) as cm:
            self.app.context.create_limit_order(
                target_symbol="SOL",
                amount=1,
                price=10,
                order_side=OrderSide.BUY,
                validate_symbol=True,
            )

        error_msg = str(cm.exception)
        self.assertIn("SOL/EUR", error_msg)
        self.assertIn("BTC/EUR", error_msg)
        self.assertIn("ETH/EUR", error_msg)
        self.assertIn("validate_symbol=False", error_msg)

    # ── create_order tests ──────────────────────────────────────────

    def test_create_order_rejects_missing_data_source(self):
        """create_order with validate_symbol=True rejects when no
        data source is registered for the pair."""
        self.app.add_strategy(StrategyOne)

        with self.assertRaises(OperationalException) as cm:
            self.app.context.create_order(
                target_symbol="BTC",
                amount=1,
                price=10,
                order_type=OrderType.LIMIT,
                order_side=OrderSide.BUY,
                validate_symbol=True,
            )

        error_msg = str(cm.exception)
        self.assertIn("BTC/EUR", error_msg)
        self.assertIn("No data source registered", error_msg)

    def test_create_order_accepts_with_matching_data_source(self):
        """create_order with validate_symbol=True passes when a
        data source exists for the pair."""
        self.app.add_strategy(StrategyOne)
        self._register_data_source("BTC/EUR")

        self.app.context.create_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_type=OrderType.LIMIT,
            order_side=OrderSide.BUY,
            validate_symbol=True,
        )
        order_repository = self.app.container.order_repository()
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertIsNotNone(order)

    def test_create_order_default_skips_validation(self):
        """create_order without validate_symbol allows any symbol."""
        self.app.add_strategy(StrategyOne)

        self.app.context.create_order(
            target_symbol="UNKNOWN",
            amount=1,
            price=10,
            order_type=OrderType.LIMIT,
            order_side=OrderSide.BUY,
        )
        order_repository = self.app.container.order_repository()
        order = order_repository.find({"target_symbol": "UNKNOWN"})
        self.assertIsNotNone(order)
