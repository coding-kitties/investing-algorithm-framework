from datetime import datetime, timezone
from importlib.util import find_spec
from math import nextafter, ulp
from types import SimpleNamespace
from unittest import TestCase, skipUnless
from unittest.mock import Mock, patch

from investing_algorithm_framework import (
    MarketCredential, PortfolioConfiguration,
)
from investing_algorithm_framework.domain import (
    OperationalException, PositionMode, TradeStatus,
)
from investing_algorithm_framework.domain.native_event import native_event_scope
from investing_algorithm_framework.services.order_service.order_service import (
    OrderService,
)
from investing_algorithm_framework.services.trade_service.trade_service import (
    TradeService,
)
from tests.resources import TestBase


MODULE = (
    "investing_algorithm_framework.services.trade_service.trade_service"
)


class TestClosingAmountRoundoff(TestCase):
    available = 0.0006575953655238284
    requested = 0.0006575953655238294

    def setUp(self):
        self.service = object.__new__(OrderService)
        self.service.position_service = Mock()
        self.position = self.service.position_service.find.return_value
        self.position.symbol = "BTC"
        self.position.get_amount.return_value = self.available
        self.position.long_amount = self.position.short_amount = self.available
        self.service.portfolio_configuration_service = Mock()
        self.service.portfolio_configuration_service.resolve_for_portfolio.return_value = None
        self.portfolio = SimpleNamespace(id=5, trading_symbol="EUR")

    def order(self, amount=None, side="SELL", order_type="LIMIT"):
        return {
            "amount": self.requested if amount is None else amount,
            "target_symbol": "BTC", "trading_symbol": "EUR",
            "order_side": side, "order_type": order_type,
            "price": 10000, "stop_price": 11000,
        }

    def test_reported_sell_quantity_is_capped_to_positive_position(self):
        order = self.order()
        self.service.validate_sell_order(order, self.portfolio)
        self.assertEqual(order["amount"], self.available)

    def test_every_sell_order_type_caps_before_reservation(self):
        for order_type in ("LIMIT", "MARKET", "STOP", "STOP_LIMIT"):
            with self.subTest(order_type=order_type):
                order = self.order(order_type=order_type)
                self.service.validate_order(order, self.portfolio)
                self.assertEqual(order["amount"], self.available)

    def test_type_level_sell_guard_caps_when_called_directly(self):
        order = self.order()
        self.service._validate_sell_amount(order, self.portfolio)
        self.assertEqual(order["amount"], self.available)

    def test_cover_quantity_uses_the_same_boundary(self):
        self.position.get_amount.return_value = -self.available
        order = self.order(side="COVER")
        self.service.validate_cover_order(order, self.portfolio)
        self.assertEqual(order["amount"], self.available)

    def test_hedge_mode_caps_against_the_matching_leg(self):
        self.service.portfolio_configuration_service.resolve_for_portfolio.return_value = (
            SimpleNamespace(position_mode=PositionMode.HEDGE)
        )
        self.position.get_amount.return_value = 0
        for side, validator in (
            ("SELL", self.service.validate_sell_order),
            ("COVER", self.service.validate_cover_order),
        ):
            with self.subTest(side=side):
                order = self.order(side=side)
                validator(order, self.portfolio)
                self.assertEqual(order["amount"], self.available)

    def test_roundoff_limit_is_bounded_and_does_not_accept_real_oversells(self):
        for delta, accepted in ((16 * ulp(self.available), True),
                                (17 * ulp(self.available), False),
                                (1e-8, False)):
            with self.subTest(delta=delta):
                order = self.order(self.available + delta)
                if accepted:
                    self.service.validate_sell_order(order, self.portfolio)
                    self.assertEqual(order["amount"], self.available)
                else:
                    with self.assertRaises(OperationalException):
                        self.service.validate_sell_order(order, self.portfolio)
                    self.assertEqual(order["amount"], self.available + delta)

    def test_valid_partial_close_is_not_changed(self):
        order = self.order(self.available / 2)
        self.service.validate_sell_order(order, self.portfolio)
        self.assertEqual(order["amount"], self.available / 2)

    def test_small_real_oversell_is_not_hidden_by_an_absolute_tolerance(self):
        self.position.get_amount.return_value = 5e-19
        with self.assertRaises(OperationalException):
            self.service.validate_sell_order(self.order(1e-18), self.portfolio)

    def test_non_finite_closing_amounts_are_rejected(self):
        for value in (float("inf"), float("nan")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(OperationalException, "finite"):
                    self.service.validate_sell_order(
                        self.order(value), self.portfolio,
                    )

    def test_reconciliation_preserves_untracked_position_units(self):
        self.position.portfolio_id = self.portfolio.id
        self.position.long_amount = 0.25
        self.position.long_cost = 25
        self.service.position_service.get.return_value = self.position
        self.service.trade_service = Mock()
        self.service.trade_service.get_all.return_value = [
            SimpleNamespace(
                id=1, is_short=False, available_amount=0.1, open_price=100,
            ),
        ]
        allocations = self.service.trade_service.trade_allocation_repository
        allocations.get_all.return_value = []
        self.service._reconcile_position_balances(
            SimpleNamespace(position_id=4, **self.order(0.1)),
        )
        self.service.position_service.update.assert_not_called()

    def test_reconciliation_without_trade_inventory_leaves_position_unchanged(self):
        self.position.portfolio_id = self.portfolio.id
        self.service.position_service.get.return_value = self.position
        self.service.trade_service = Mock()
        self.service.trade_service.get_all.return_value = []
        self.service._reconcile_position_balances(
            SimpleNamespace(position_id=4, **self.order(1)),
        )
        self.service.position_service.update.assert_not_called()


class TestTradeAmountRoundoff(TestCase):
    def setUp(self):
        self.timestamp = datetime(2020, 1, 1, tzinfo=timezone.utc)
        self.trade = Mock(
            id=1, available_amount=0.01, open_price=100,
            net_gain=0, total_fees=0, is_short=False,
            status=TradeStatus.OPEN.value,
            buy_order=SimpleNamespace(order_fee=0, filled=0.01),
        )
        self.order = SimpleNamespace(
            id=2, amount=nextafter(0.01, 0), price=100,
            updated_at=self.timestamp, order_fee=0,
        )
        self.allocation = SimpleNamespace(
            id=3, trade_id=1, amount=0.01, amount_pending=0.01,
            open_price=100, close_price=0, buy_fee=0, sell_fee=0,
            net_gain_contribution=0, stop_loss_id=None, take_profit_id=None,
        )
        self.service = object.__new__(TradeService)
        self.service.repository = Mock()
        self.service.repository.get.return_value = self.trade
        self.service.repository.update.side_effect = self._update_trade
        self.service.order_repository = Mock()
        self.service.order_repository.get.return_value = self.order
        self.service.trade_allocation_repository = Mock()
        self.service.trade_allocation_repository.get_all.return_value = [
            self.allocation,
        ]
        self.service.trade_stop_loss_repository = Mock()
        self.service.position_repository = Mock()
        self.service.position_repository.find.return_value = SimpleNamespace(
            id=4, portfolio_id=5, long_cost=1,
        )
        self.service.portfolio_repository = Mock()
        self.service.portfolio_repository.get.return_value = SimpleNamespace(
            id=5, total_net_gain=0, net_size=1000, total_revenue=0,
        )
        self.service.trade_hook_dispatcher = None

    def _update_trade(self, trade_id, values):
        self.assertEqual(trade_id, self.trade.id)
        for name, value in values.items():
            setattr(self.trade, name, value)
        return self.trade

    def test_full_reservation_does_not_leave_one_ulp_available(self):
        with patch(f"{MODULE}.native_event_engine", return_value=None):
            self.service._allocate_sell_to_trade(
                self.trade.id, self.order, self.order.amount,
            )
        self.assertEqual(self.trade.available_amount, 0)

    def test_native_reservation_does_not_leave_one_ulp_available(self):
        self.service._allocate_sell_to_trade(
            self.trade.id, self.order, self.order.amount,
            next_available=0.01 - self.order.amount,
        )
        self.assertEqual(self.trade.available_amount, 0)

    def test_aggregate_close_does_not_leave_dust_in_a_smaller_last_lot(self):
        self.trade.available_amount = 0.0002
        self.order.amount = 0.1002
        self.service._allocate_sell_to_trade(
            self.trade.id, self.order, self.order.amount - 0.1,
        )
        self.assertEqual(self.trade.available_amount, 0)

    def test_aggregate_fill_clears_pending_roundoff_in_a_smaller_last_lot(self):
        first_trade = Mock(
            id=8, available_amount=0, open_price=100, net_gain=0,
            total_fees=0, is_short=False, status=TradeStatus.OPEN.value,
            buy_order=SimpleNamespace(order_fee=0, filled=0.1),
        )
        first_allocation = SimpleNamespace(
            **{
                **vars(self.allocation), "id": 9, "trade_id": 8,
                "amount": 0.1, "amount_pending": 0.1,
            },
        )
        self.trade.available_amount = 0
        self.allocation.amount = self.allocation.amount_pending = 0.0002
        self.order.amount = 0.1002
        trades = {1: self.trade, 8: first_trade}
        allocations = [first_allocation, self.allocation]
        self.service.repository.get.side_effect = trades.__getitem__

        def update(trade_id, values):
            trade = trades[trade_id]
            for name, value in values.items():
                setattr(trade, name, value)
            return trade

        self.service.repository.update.side_effect = update
        self.service.trade_allocation_repository.get_all.side_effect = (
            lambda query: allocations if "order_id" in query else [
                item for item in allocations
                if item.trade_id == query["trade_id"]
            ]
        )
        with patch(f"{MODULE}.native_event_engine", return_value=None):
            self.service.update_trade_with_filled_sell_order(
                self.order.amount, self.order,
            )
        self.assertEqual(first_allocation.amount_pending, 0)
        self.assertEqual(self.allocation.amount_pending, 0)
        self.assertEqual(first_trade.status, TradeStatus.CLOSED.value)
        self.assertEqual(self.trade.status, TradeStatus.CLOSED.value)

    def test_filled_close_does_not_release_roundoff_back_to_trade(self):
        self.trade.available_amount = 0
        with patch(f"{MODULE}.native_event_engine", return_value=None):
            self.service.update_trade_with_filled_sell_order(
                self.order.amount, self.order,
            )
        self.assertEqual(self.trade.available_amount, 0)
        self.assertEqual(self.allocation.amount_pending, 0)
        self.assertEqual(self.trade.status, TradeStatus.CLOSED.value)
        self.assertEqual(self.trade.closed_at, self.timestamp)

    def test_native_filled_close_normalizes_pending_roundoff(self):
        self.trade.available_amount = 0
        native = Mock()
        native.event_sell_plan.return_value = (
            [(0, 0.01 - self.order.amount, 100, 0, 0, 0, 0, 0)],
            self.order.amount * 100, 0,
        )
        with patch(f"{MODULE}.native_event_engine", return_value=native), patch.object(
            self.service, "_settle_native_exit_totals",
        ):
            self.service.update_trade_with_filled_sell_order(
                self.order.amount, self.order,
            )
        self.assertEqual(self.trade.available_amount, 0)
        self.assertEqual(self.allocation.amount_pending, 0)
        self.assertEqual(self.trade.status, TradeStatus.CLOSED.value)

    def test_real_order_reduction_releases_unfilled_trade_amount(self):
        self.trade.available_amount = 0
        self.order.amount = 0.009
        with patch(f"{MODULE}.native_event_engine", return_value=None):
            self.service.update_trade_with_filled_sell_order(
                self.order.amount, self.order,
            )
        self.assertAlmostEqual(self.trade.available_amount, 0.001)
        self.assertEqual(self.trade.status, TradeStatus.OPEN.value)
        self.assertEqual(self.allocation.amount_pending, 0)

    def test_genuine_tiny_partial_position_is_not_discarded(self):
        self.trade.available_amount = 1e-18
        self.order.amount = 5e-19
        self.service._allocate_sell_to_trade(
            self.trade.id, self.order, 5e-19,
        )
        self.assertEqual(self.trade.available_amount, 5e-19)

    def test_non_finite_amounts_fail_before_creating_allocations(self):
        for value in (float("inf"), float("nan")):
            with self.subTest(value=value):
                self.trade.available_amount = value
                with self.assertRaisesRegex(OperationalException, "finite"):
                    self.service._allocate_sell_to_trade(
                        self.trade.id, self.order, 0.01,
                    )
        self.service.trade_allocation_repository.create.assert_not_called()

    def test_order_validation_still_rejects_sells_against_empty_positions(self):
        service = object.__new__(OrderService)
        service.position_service = Mock()
        service.position_service.find.return_value.get_amount.return_value = 0
        portfolio = SimpleNamespace(id=5, trading_symbol="EUR")
        order = {
            "amount": 1.6263032587282567e-18,
            "target_symbol": "BTC", "trading_symbol": "EUR",
        }
        with patch.object(
            service, "_position_mode", return_value=PositionMode.NETTING,
        ), self.assertRaisesRegex(OperationalException, "open position 0"):
            service.validate_sell_order(order, portfolio)

    def test_pending_trade_without_available_amount_cannot_emit_stop_order(self):
        stop_loss = SimpleNamespace(
            id=6, active=True, sold_amount=0,
            has_triggered=Mock(return_value=True),
            get_sell_amount=Mock(return_value=0.01),
            add_sell_price=Mock(),
        )
        self.trade.available_amount = 0
        self.trade.stop_losses = [stop_loss]
        self.trade.last_reported_price = 90
        self.trade.last_reported_price_datetime = self.timestamp
        self.trade.target_symbol = "BTC"
        self.trade.trading_symbol = "EUR"
        self.trade.orders = [SimpleNamespace(id=7)]
        self.trade.filled_amount = self.trade.amount = 0.01
        self.service.repository.get_all.return_value = [self.trade]
        self.assertEqual(self.service.get_triggered_stop_loss_orders(), [])
        self.assertTrue(stop_loss.active)
        stop_loss.has_triggered.assert_not_called()


class TestProtectiveCloseRoundoff(TestBase):
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance", api_key="api_key", secret_key="secret_key",
        ),
    ]
    portfolio_configurations = [
        PortfolioConfiguration(market="binance", trading_symbol="EUR"),
    ]
    external_balances = {"EUR": 1000}

    def _close_with_risk_rule(
        self, risk, large_lot=False, pending=False, lot_amount=None, short=False,
    ):
        requested = (
            (0.005414754029673499 if lot_amount is None else lot_amount)
            if large_lot
            else TestClosingAmountRoundoff.requested
        )
        available = (
            requested if large_lot else TestClosingAmountRoundoff.available
        )
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()
        position_service = self.app.container.position_service()
        lookup = self.app.container.order_executor_lookup()
        lookup.register_order_executor_for_market("binance")
        executor = lookup.get_order_executor("binance")
        if large_lot:
            executor.order_amount_filled = 1
            large_buy = order_service.create({
                "target_symbol": "BTC", "trading_symbol": "EUR",
                "amount": 1, "order_side": "SHORT" if short else "BUY",
                "price": 100,
                "order_type": "LIMIT", "portfolio_id": 1,
            })
            large_trade = trade_service.find({"order_id": large_buy.id})
        executor.order_amount_filled = requested
        buy = order_service.create({
            "target_symbol": "BTC", "trading_symbol": "EUR",
            "amount": requested, "order_side": "SHORT" if short else "BUY",
            "price": 10000,
            "order_type": "LIMIT", "portfolio_id": 1,
        })
        trade = trade_service.find({"order_id": buy.id})
        self.assertEqual(trade.available_amount, requested)
        if large_lot:
            executor.order_amount_filled = 0 if pending else 1
            order_service.create({
                "target_symbol": "BTC", "trading_symbol": "EUR",
                "amount": 1, "order_side": "COVER" if short else "SELL",
                "price": 100,
                "order_type": "LIMIT", "portfolio_id": 1,
                "trades": [{"trade_id": large_trade.id, "amount": 1}],
            })
            self.assertEqual(
                position_service.get(buy.position_id).amount,
                -requested if short else requested,
            )
        else:
            position_service.update(buy.position_id, {"amount": available})
        timestamp = datetime.now(timezone.utc)
        if risk == "stop_loss":
            trade_service.add_stop_loss(
                trade=trade, percentage=10, created_at=timestamp,
            )
            price = 11100 if short else 8800
            triggered_orders = trade_service.get_triggered_stop_loss_orders
        else:
            trade_service.add_take_profit(
                trade=trade, percentage=10, created_at=timestamp,
            )
            price = 8800 if short else 11100
            triggered_orders = trade_service.get_triggered_take_profit_orders
        trade_service.update(trade.id, {
            "last_reported_price": price,
            "last_reported_price_datetime": timestamp,
        })
        pending_orders = triggered_orders()
        self.assertEqual(len(pending_orders), 1)
        self.assertEqual(pending_orders[0]["amount"], requested)
        executor.order_amount_filled = available
        close = order_service.create(pending_orders[0])
        self.assertEqual(close.amount, available)
        self.assertEqual(close.filled, available)
        self.assertEqual(position_service.get(buy.position_id).amount, 0)
        self.assertEqual(
            getattr(
                position_service.get(buy.position_id),
                "short_cost" if short else "long_cost",
            ),
            100 if pending else 0,
        )
        closed_trade = trade_service.get(trade.id)
        self.assertEqual(closed_trade.available_amount, 0)
        self.assertEqual(closed_trade.status, TradeStatus.CLOSED.value)
        allocations = self.app.container.trade_allocation_repository().get_all({
            "order_id": close.id,
        })
        self.assertEqual(len(allocations), 1 if short else 2)
        self.assertTrue(all(item.amount_pending == 0 for item in allocations))
        self.assertEqual(triggered_orders(), [])

    def test_reported_quantities_close_stop_loss_without_oversell_or_dust(self):
        self._close_with_risk_rule("stop_loss")

    def test_reported_quantities_close_take_profit_without_oversell_or_dust(self):
        self._close_with_risk_rule("take_profit")

    def test_small_lot_stop_survives_closing_a_larger_lot(self):
        self._close_with_risk_rule("stop_loss", large_lot=True)

    def test_small_lot_take_profit_survives_closing_a_larger_lot(self):
        self._close_with_risk_rule("take_profit", large_lot=True)

    def test_pending_large_sell_preserves_small_lot_stop(self):
        self._close_with_risk_rule("stop_loss", large_lot=True, pending=True)

    def test_pending_large_sell_preserves_small_lot_take_profit(self):
        self._close_with_risk_rule("take_profit", large_lot=True, pending=True)

    def test_large_close_preserves_a_genuinely_tiny_remaining_lot(self):
        self._close_with_risk_rule(
            "stop_loss", large_lot=True, lot_amount=1e-18,
        )

    def test_small_short_lot_stop_survives_covering_a_larger_lot(self):
        self._close_with_risk_rule("stop_loss", large_lot=True, short=True)

    def test_small_short_lot_take_profit_survives_covering_a_larger_lot(self):
        self._close_with_risk_rule("take_profit", large_lot=True, short=True)

    @skipUnless(find_spec("iaf_confluence_native"), "Native backend unavailable")
    def test_native_small_lot_stop_survives_closing_a_larger_lot(self):
        with native_event_scope("rust"):
            self._close_with_risk_rule("stop_loss", large_lot=True)

    @skipUnless(find_spec("iaf_confluence_native"), "Native backend unavailable")
    def test_native_pending_large_sell_preserves_small_lot_take_profit(self):
        with native_event_scope("rust"):
            self._close_with_risk_rule(
                "take_profit", large_lot=True, pending=True,
            )

    @skipUnless(find_spec("iaf_confluence_native"), "Native backend unavailable")
    def test_native_large_close_preserves_a_genuinely_tiny_remaining_lot(self):
        with native_event_scope("rust"):
            self._close_with_risk_rule(
                "stop_loss", large_lot=True, lot_amount=1e-18,
            )

    @skipUnless(find_spec("iaf_confluence_native"), "Native backend unavailable")
    def test_native_small_short_lot_stop_survives_covering_a_larger_lot(self):
        with native_event_scope("rust"):
            self._close_with_risk_rule(
                "stop_loss", large_lot=True, short=True,
            )
