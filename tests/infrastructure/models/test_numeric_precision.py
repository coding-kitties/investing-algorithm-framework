"""
Tests to verify that numeric values are stored as TEXT in SQLite via
SqliteDecimal, preserving full precision in the database.

SqliteDecimal stores values as TEXT (lossless) and returns float for
backward compatibility. These tests verify:
1. Values within float64 precision (~15 significant digits) round-trip.
2. The raw SQLite storage is TEXT (not REAL), preserving exact values.
3. Order amount, order price, balance, and position fields all work.
"""
from decimal import Decimal

from sqlalchemy import text

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
from investing_algorithm_framework.infrastructure.database import Session
from tests.resources import TestBase


class TestOrderNumericPrecision(TestBase):
    """Verify order price and amount survive a DB round-trip."""
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
            initial_balance=999999999999999.0,
        )
    ]
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]
    external_balances = {"EUR": 999999999999999.0}

    def test_large_order_amount(self):
        """Order amount with many significant digits must round-trip."""
        order_service = self.app.container.order_service()
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})

        # 15 significant digits - within float64 precision
        amount = 123456789012.345
        order = order_service.create({
            "target_symbol": "BTC",
            "trading_symbol": "EUR",
            "price": 1.0,
            "amount": amount,
            "order_side": "BUY",
            "order_type": "LIMIT",
            "portfolio_id": portfolio.id,
        })

        retrieved = order_service.find({"id": order.id})
        self.assertEqual(retrieved.get_amount(), amount)

    def test_large_order_price(self):
        """Order price with many significant digits must round-trip."""
        order_service = self.app.container.order_service()
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})

        price = 98765432109.8765
        order = order_service.create({
            "target_symbol": "ETH",
            "trading_symbol": "EUR",
            "price": price,
            "amount": 1.0,
            "order_side": "BUY",
            "order_type": "LIMIT",
            "portfolio_id": portfolio.id,
        })

        retrieved = order_service.find({"id": order.id})
        self.assertEqual(retrieved.get_price(), price)

    def test_small_crypto_amount(self):
        """Very small crypto amounts (sub-satoshi) must round-trip."""
        order_service = self.app.container.order_service()
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})

        tiny_amount = 0.00000001234567
        order = order_service.create({
            "target_symbol": "BTC",
            "trading_symbol": "EUR",
            "price": 50000.0,
            "amount": tiny_amount,
            "order_side": "BUY",
            "order_type": "LIMIT",
            "portfolio_id": portfolio.id,
        })

        retrieved = order_service.find({"id": order.id})
        self.assertEqual(retrieved.get_amount(), tiny_amount)

    def test_order_fee_fields(self):
        """Order fee and fee rate must round-trip."""
        order_service = self.app.container.order_service()
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})

        order = order_service.create({
            "target_symbol": "BTC",
            "trading_symbol": "EUR",
            "price": 50000.0,
            "amount": 1.0,
            "order_side": "BUY",
            "order_type": "LIMIT",
            "portfolio_id": portfolio.id,
        })

        fee = 0.00123456789012
        fee_rate = 0.001
        order_service.update(order.id, {
            "order_fee": fee,
            "order_fee_rate": fee_rate,
        })
        retrieved = order_service.find({"id": order.id})
        self.assertEqual(retrieved.get_order_fee(), fee)
        self.assertEqual(retrieved.get_order_fee_rate(), fee_rate)

    def test_order_amount_stored_as_text(self):
        """Verify the raw SQLite column stores values as TEXT, not REAL."""
        order_service = self.app.container.order_service()
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})

        amount = 12345678901234.5
        order = order_service.create({
            "target_symbol": "XRP",
            "trading_symbol": "EUR",
            "price": 1.0,
            "amount": amount,
            "order_side": "BUY",
            "order_type": "LIMIT",
            "portfolio_id": portfolio.id,
        })

        with Session() as db:
            row = db.execute(text(
                "SELECT typeof(amount), amount FROM orders WHERE id = :id"
            ), {"id": order.id}).fetchone()
            self.assertEqual(row[0], "text",
                             "amount column should be stored as TEXT")
            # The stored text should be the exact Decimal representation
            self.assertEqual(row[1], str(Decimal(str(amount))))

    def test_order_price_stored_as_text(self):
        """Verify the raw SQLite column stores price as TEXT."""
        order_service = self.app.container.order_service()
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})

        price = 12345678901234.5
        order = order_service.create({
            "target_symbol": "DOT",
            "trading_symbol": "EUR",
            "price": price,
            "amount": 1.0,
            "order_side": "BUY",
            "order_type": "LIMIT",
            "portfolio_id": portfolio.id,
        })

        with Session() as db:
            row = db.execute(text(
                "SELECT typeof(price), price FROM orders WHERE id = :id"
            ), {"id": order.id}).fetchone()
            self.assertEqual(row[0], "text")
            # The full precision string must be stored in the DB
            self.assertEqual(row[1], str(Decimal(str(price))))


class TestPortfolioBalancePrecision(TestBase):
    """Verify portfolio balance fields survive DB round-trip."""
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
            initial_balance=999999999999.99,
        )
    ]
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]
    external_balances = {"EUR": 999999999999.99}

    def test_large_balance_roundtrip(self):
        """A large initial balance must round-trip."""
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})
        self.assertEqual(portfolio.get_unallocated(), 999999999999.99)

    def test_balance_update(self):
        """Updating unallocated balance must preserve the value."""
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})
        new_balance = 555555555555.555
        portfolio_service.update(
            portfolio.id, {"unallocated": new_balance}
        )
        updated = portfolio_service.find({"market": "binance"})
        self.assertEqual(updated.get_unallocated(), new_balance)

    def test_portfolio_financial_fields(self):
        """All financial fields on a portfolio must round-trip."""
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})

        expected_realized = 111111111111.11
        expected_revenue = 222222222222.22
        expected_cost = 333333333333.33
        expected_net_gain = 444444444444.44
        expected_trade_volume = 555555555555.55
        expected_net_size = 666666666666.66

        portfolio_service.update(portfolio.id, {
            "realized": expected_realized,
            "total_revenue": expected_revenue,
            "total_cost": expected_cost,
            "total_net_gain": expected_net_gain,
            "total_trade_volume": expected_trade_volume,
            "net_size": expected_net_size,
        })
        updated = portfolio_service.find({"market": "binance"})

        self.assertEqual(updated.get_realized(), expected_realized)
        self.assertEqual(updated.get_total_revenue(), expected_revenue)
        self.assertEqual(updated.get_total_cost(), expected_cost)
        self.assertEqual(updated.get_total_net_gain(), expected_net_gain)
        self.assertEqual(updated.get_total_trade_volume(), expected_trade_volume)
        self.assertEqual(updated.get_net_size(), expected_net_size)

    def test_balance_stored_as_text(self):
        """Verify the raw SQLite storage is TEXT for unallocated."""
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})

        with Session() as db:
            row = db.execute(text(
                "SELECT typeof(unallocated), unallocated "
                "FROM portfolios WHERE id = :id"
            ), {"id": portfolio.id}).fetchone()
            self.assertEqual(row[0], "text",
                             "unallocated column should be stored as TEXT")

    def test_large_decimal_balance_stored_exactly(self):
        """A Decimal balance with >15 digits is stored exactly in TEXT."""
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})

        # This value has >15 significant digits - would be lossy as float
        exact_str = "12345678901234.567890123456789"
        portfolio_service.update(
            portfolio.id, {"unallocated": Decimal(exact_str)}
        )

        with Session() as db:
            row = db.execute(text(
                "SELECT unallocated FROM portfolios WHERE id = :id"
            ), {"id": portfolio.id}).fetchone()
            # The raw TEXT in SQLite preserves the exact Decimal representation
            self.assertEqual(row[0], exact_str)


class TestPositionNumericPrecision(TestBase):
    """Verify position amount and cost survive DB round-trip."""
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="USDT"
        )
    ]
    market_credentials = [
        MarketCredential(
            market="BITVAVO",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]
    external_balances = {"USDT": 1000}

    def test_large_position_amount(self):
        """A position with a large amount must round-trip."""
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "BITVAVO"})
        position_repository = self.app.container.position_repository()

        large_amount = 123456789012.345
        position_repository.create({
            "symbol": "BTC",
            "amount": large_amount,
            "portfolio_id": portfolio.id,
        })
        position = position_repository.find({
            "symbol": "BTC", "portfolio": portfolio.id
        })
        self.assertEqual(position.get_amount(), large_amount)

    def test_large_position_cost(self):
        """A position with a large cost must round-trip."""
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "BITVAVO"})
        position_repository = self.app.container.position_repository()

        large_cost = 98765432109.8765
        position_repository.create({
            "symbol": "ETH",
            "amount": 1.0,
            "cost": large_cost,
            "portfolio_id": portfolio.id,
        })
        position = position_repository.find({
            "symbol": "ETH", "portfolio": portfolio.id
        })
        self.assertEqual(position.get_cost(), large_cost)

    def test_tiny_position_amount(self):
        """A very small position amount must round-trip."""
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "BITVAVO"})
        position_repository = self.app.container.position_repository()

        tiny_amount = 0.000000000001234
        position_repository.create({
            "symbol": "SHIB",
            "amount": tiny_amount,
            "portfolio_id": portfolio.id,
        })
        position = position_repository.find({
            "symbol": "SHIB", "portfolio": portfolio.id
        })
        self.assertEqual(position.get_amount(), tiny_amount)

    def test_position_amount_update(self):
        """Updating a position amount must preserve the value."""
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "BITVAVO"})
        position_repository = self.app.container.position_repository()

        position_repository.create({
            "symbol": "SOL",
            "amount": 100.0,
            "portfolio_id": portfolio.id,
        })
        position = position_repository.find({
            "symbol": "SOL", "portfolio": portfolio.id
        })

        new_amount = 999999999999.999
        position_repository.update(position.id, {"amount": new_amount})
        updated = position_repository.find({
            "symbol": "SOL", "portfolio": portfolio.id
        })
        self.assertEqual(updated.get_amount(), new_amount)

    def test_position_amount_stored_as_text(self):
        """Verify the raw SQLite column stores amount as TEXT."""
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "BITVAVO"})
        position_repository = self.app.container.position_repository()

        # Store a Decimal with full precision
        exact_str = "12345678901234.567890123456789"
        position_repository.create({
            "symbol": "ADA",
            "amount": Decimal(exact_str),
            "portfolio_id": portfolio.id,
        })
        position = position_repository.find({
            "symbol": "ADA", "portfolio": portfolio.id
        })

        with Session() as db:
            row = db.execute(text(
                "SELECT typeof(amount), amount FROM positions WHERE id = :id"
            ), {"id": position.id}).fetchone()
            self.assertEqual(row[0], "text",
                             "amount column should be stored as TEXT")
            # The exact string is preserved in the database
            self.assertEqual(row[1], exact_str)
