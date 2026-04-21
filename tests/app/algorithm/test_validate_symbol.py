from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, OrderSide
from investing_algorithm_framework.domain import OperationalException
from tests.resources import TestBase
from tests.resources.strategies_for_testing import StrategyOne


class TestValidateSymbol(TestBase):
    """Tests for opt-in symbol validation on order creation (issue #247).

    Validates that target_symbol is not the same as trading_symbol,
    which would result in a nonsensical order (e.g. EUR/EUR).
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

    def test_default_allows_trading_symbol_as_target(self):
        """Default behavior: no validation, even trading_symbol is accepted."""
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

    def test_validate_symbol_false_allows_trading_symbol_as_target(self):
        """Explicit validate_symbol=False allows trading_symbol as target."""
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

    def test_validate_symbol_true_rejects_trading_symbol_as_target(self):
        """validate_symbol=True raises when target_symbol equals
        trading_symbol (e.g. EUR/EUR)."""
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
        self.assertIn("EUR", error_msg)
        self.assertIn("trading_symbol", error_msg)
        self.assertIn("EUR/EUR", error_msg)

    def test_validate_symbol_true_case_insensitive(self):
        """validate_symbol=True catches trading_symbol regardless of case."""
        self.app.add_strategy(StrategyOne)

        with self.assertRaises(OperationalException):
            self.app.context.create_limit_order(
                target_symbol="eur",
                amount=1,
                price=10,
                order_side=OrderSide.BUY,
                validate_symbol=True,
            )

    def test_validate_symbol_true_accepts_valid_target(self):
        """validate_symbol=True passes for a target that differs
        from trading_symbol."""
        self.app.add_strategy(StrategyOne)

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

    def test_validate_symbol_error_message(self):
        """Error message explains the EUR/EUR problem and how to skip."""
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
        self.assertIn("validate_symbol=False", error_msg)
