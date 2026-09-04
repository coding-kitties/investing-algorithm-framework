"""Service-level tests for the mirror stop-loss/take-profit safety-net
data plumbing (mirror_on_exchange flag threaded end-to-end, plus
mark_triggered(mirror=True) bookkeeping). No exchange calls are made
here yet — this only verifies the flag survives from rule attachment
through fill-time materialization onto the trade, and that
mark_triggered can record a mirror-driven trigger distinctly from a
client-side one.
"""
from datetime import datetime, timezone
from unittest.mock import patch

from investing_algorithm_framework.services import DefaultTradeOrderEvaluator

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, OrderStatus, TradeStatus
from tests.resources import TestBase


def _now():
    return datetime.now(tz=timezone.utc)


class TestMirrorStopLossTakeProfit(TestBase):
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR"
        )
    ]
    external_balances = {"EUR": 1000}

    def test_pending_stop_loss_mirror_flag_materializes_at_fill(self):
        order_repository = self.app.container.order_repository()
        trade_service = self.app.container.trade_service()

        buy_order = order_repository.create({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 100,
            "filled": 0,
            "order_side": "BUY",
            "price": 10,
            "order_type": "LIMIT",
            "status": OrderStatus.OPEN.value,
        })

        trade_service.add_stop_loss(
            order=buy_order, percentage=5, trailing=False,
            mirror_on_exchange=True,
        )

        trade = trade_service.create_trade_at_fill(
            buy_order, 100, 10, _now()
        )
        # Re-fetch: the object returned by create_trade_at_fill predates
        # the pending-rule materialization loop refreshing its
        # relationships, mirroring the existing short-order test pattern.
        trade = trade_service.get(trade.id)

        self.assertEqual(1, len(trade.stop_losses))
        self.assertTrue(trade.stop_losses[0].mirror_on_exchange)

    def test_pending_take_profit_without_mirror_flag_defaults_false(self):
        order_repository = self.app.container.order_repository()
        trade_service = self.app.container.trade_service()

        buy_order = order_repository.create({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 100,
            "filled": 0,
            "order_side": "BUY",
            "price": 10,
            "order_type": "LIMIT",
            "status": OrderStatus.OPEN.value,
        })

        # No mirror_on_exchange kwarg passed here — should default False.
        trade_service.add_take_profit(
            order=buy_order, percentage=5, trailing=False,
        )

        trade = trade_service.create_trade_at_fill(
            buy_order, 100, 10, _now()
        )
        trade = trade_service.get(trade.id)

        self.assertEqual(1, len(trade.take_profits))
        self.assertFalse(trade.take_profits[0].mirror_on_exchange)

    def test_add_stop_loss_direct_to_trade_with_mirror_flag(self):
        order_repository = self.app.container.order_repository()
        trade_service = self.app.container.trade_service()

        buy_order = order_repository.create({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 100,
            "filled": 100,
            "order_side": "BUY",
            "price": 10,
            "order_type": "LIMIT",
            "status": OrderStatus.CLOSED.value,
        })
        trade = trade_service.create_trade_at_fill(
            buy_order, 100, 10, _now()
        )

        stop_loss = trade_service.add_stop_loss(
            trade=trade, percentage=5, trailing=False,
            mirror_on_exchange=True,
        )

        self.assertTrue(stop_loss.mirror_on_exchange)
        self.assertIsNone(stop_loss.mirror_order_id)
        self.assertFalse(stop_loss.mirror_triggered)

    def test_mark_triggered_mirror_true_sets_mirror_fields_only(self):
        order_repository = self.app.container.order_repository()
        trade_service = self.app.container.trade_service()
        trade_stop_loss_service = self.app.container.trade_stop_loss_service()

        buy_order = order_repository.create({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 100,
            "filled": 100,
            "order_side": "BUY",
            "price": 10,
            "order_type": "LIMIT",
            "status": OrderStatus.CLOSED.value,
        })
        trade = trade_service.create_trade_at_fill(
            buy_order, 100, 10, _now()
        )
        stop_loss = trade_service.add_stop_loss(
            trade=trade, percentage=5, trailing=False,
            mirror_on_exchange=True,
        )

        trigger_date = _now()
        trade_stop_loss_service.mark_triggered(
            [stop_loss.id], trigger_date, mirror=True
        )

        updated = trade_stop_loss_service.get(stop_loss.id)
        self.assertTrue(updated.triggered)
        self.assertTrue(updated.mirror_triggered)
        self.assertIsNotNone(updated.mirror_triggered_at)

    def test_mark_triggered_default_does_not_set_mirror_fields(self):
        order_repository = self.app.container.order_repository()
        trade_service = self.app.container.trade_service()
        trade_take_profit_service = \
            self.app.container.trade_take_profit_service()

        buy_order = order_repository.create({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 100,
            "filled": 100,
            "order_side": "BUY",
            "price": 10,
            "order_type": "LIMIT",
            "status": OrderStatus.CLOSED.value,
        })
        trade = trade_service.create_trade_at_fill(
            buy_order, 100, 10, _now()
        )
        take_profit = trade_service.add_take_profit(
            trade=trade, percentage=5, trailing=False,
        )

        trade_take_profit_service.mark_triggered(
            [take_profit.id], _now()
        )

        updated = trade_take_profit_service.get(take_profit.id)
        self.assertTrue(updated.triggered)
        self.assertFalse(updated.mirror_triggered)
        self.assertIsNone(updated.mirror_triggered_at)


class TestMirrorOrderPlacement(TestBase):
    """
    End-to-end: a mirror_on_exchange stop-loss attached to a BUY order
    causes a resting broker-native STOP order to be placed once the
    trade opens, and correctly closes the trade once THAT order is
    observed to fill -- without ever prematurely closing the trade at
    placement time.
    """
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR"
        )
    ]
    external_balances = {"EUR": 1000}

    def test_mirror_stop_loss_order_placed_and_closes_trade_on_fill(self):
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()
        trade_stop_loss_service = self.app.container.trade_stop_loss_service()
        order_repository = self.app.container.order_repository()

        buy_order = order_service.create({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 20,
            "order_side": "BUY",
            "price": 10,
            "order_type": "LIMIT",
            "portfolio_id": 1,
        })
        trade_service.add_stop_loss(
            order=buy_order, percentage=10, trailing=False,
            mirror_on_exchange=True,
        )

        # Fill the buy order -- materializes the SL onto the new
        # trade and should place a resting mirror STOP order.
        order_service.update(
            buy_order.id,
            {"filled": 20, "remaining": 0, "status": OrderStatus.CLOSED.value}
        )

        trade = trade_service.find({"order_id": buy_order.id})
        stop_loss = trade.stop_losses[0]
        self.assertIsNotNone(stop_loss.mirror_order_id)

        mirror_order = order_repository.get(stop_loss.mirror_order_id)
        self.assertEqual("STOP", mirror_order.order_type)
        self.assertEqual("SELL", mirror_order.order_side)
        self.assertEqual(9.0, mirror_order.stop_price)
        self.assertEqual(
            "stop_loss_mirror", mirror_order.metadata.get("order_reason")
        )

        # Placement must NOT prematurely close the trade or touch
        # available_amount -- only an actual fill of the mirror order
        # may do that.
        trade = trade_service.get(trade.id)
        self.assertEqual(TradeStatus.OPEN.value, trade.status)
        self.assertEqual(20, trade.available_amount)

        # Simulate the mirror order actually filling on the exchange.
        order_service.update(
            mirror_order.id,
            {
                "filled": 20, "remaining": 0,
                "status": OrderStatus.CLOSED.value
            }
        )

        trade = trade_service.get(trade.id)
        self.assertEqual(TradeStatus.CLOSED.value, trade.status)
        self.assertEqual(0, trade.available_amount)

        stop_loss = trade_stop_loss_service.get(stop_loss.id)
        self.assertTrue(stop_loss.triggered)
        self.assertTrue(stop_loss.mirror_triggered)
        self.assertIsNotNone(stop_loss.mirror_triggered_at)
        self.assertFalse(stop_loss.active)


class TestMirrorOrderCancellation(TestBase):
    """
    A resting mirror order must be cancelled the moment the trade
    closes through any OTHER route -- a client-side trigger on a
    sibling (non-mirrored) rule, or a manual close -- so it can never
    also fire independently afterwards.
    """
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR"
        )
    ]
    external_balances = {"EUR": 1000}

    def _open_trade_with_mirrored_stop_loss_and_plain_take_profit(self):
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()

        buy_order = order_service.create({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 20,
            "order_side": "BUY",
            "price": 10,
            "order_type": "LIMIT",
            "portfolio_id": 1,
        })
        trade_service.add_stop_loss(
            order=buy_order, percentage=10, trailing=False,
            mirror_on_exchange=True,
        )
        trade_service.add_take_profit(
            order=buy_order, percentage=5, trailing=False,
        )
        order_service.update(
            buy_order.id,
            {"filled": 20, "remaining": 0, "status": OrderStatus.CLOSED.value}
        )
        return trade_service.find({"order_id": buy_order.id})

    def test_client_side_take_profit_trigger_cancels_resting_sl_mirror(self):
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()
        order_repository = self.app.container.order_repository()

        trade = self.\
            _open_trade_with_mirrored_stop_loss_and_plain_take_profit()
        stop_loss = trade.stop_losses[0]
        self.assertIsNotNone(stop_loss.mirror_order_id)
        mirror_order = order_repository.get(stop_loss.mirror_order_id)
        self.assertEqual(OrderStatus.OPEN.value, mirror_order.status)

        # Push the price up to the (non-mirrored) take-profit trigger.
        trade_service.update(trade.id, {
            "last_reported_price": 10.5,
            "last_reported_price_datetime": _now(),
        })

        evaluator = DefaultTradeOrderEvaluator(
            trade_service=trade_service,
            order_service=order_service,
            trade_stop_loss_service=self.app.container
            .trade_stop_loss_service(),
            trade_take_profit_service=self.app.container
            .trade_take_profit_service(),
            configuration_service=self.app.container
            .configuration_service(),
            context=self.app.context,
        )
        evaluator._check_take_profits()

        mirror_order = order_repository.get(stop_loss.mirror_order_id)
        self.assertEqual(OrderStatus.CANCELED.value, mirror_order.status)

        trade = trade_service.get(trade.id)
        self.assertEqual(TradeStatus.CLOSED.value, trade.status)

    def test_manual_close_trade_cancels_resting_mirror_order(self):
        order_repository = self.app.container.order_repository()

        trade = self.\
            _open_trade_with_mirrored_stop_loss_and_plain_take_profit()
        stop_loss = trade.stop_losses[0]
        self.assertIsNotNone(stop_loss.mirror_order_id)

        with patch.object(
            self.app.container.data_provider_service(),
            "get_ticker_data",
            return_value={"bid": 10, "ask": 10.5, "last": 10.25},
        ):
            self.app.context.close_trade(trade)

        mirror_order = order_repository.get(stop_loss.mirror_order_id)
        self.assertEqual(OrderStatus.CANCELED.value, mirror_order.status)


class TestMirrorOrderOverlap(TestBase):
    """
    A mirrored stop-loss and a mirrored take-profit on the SAME trade
    must never both promise the trade's full amount at once -- neither
    reserves the position at placement time, so nothing else stops
    that -- and whichever one fires first must clean up the other's
    still-resting mirror order.
    """
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR"
        )
    ]
    external_balances = {"EUR": 1000}

    def _open_trade_with_both_mirrored(self):
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()

        buy_order = order_service.create({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 20,
            "order_side": "BUY",
            "price": 10,
            "order_type": "LIMIT",
            "portfolio_id": 1,
        })
        trade_service.add_stop_loss(
            order=buy_order, percentage=10, trailing=False,
            sell_percentage=100, mirror_on_exchange=True,
        )
        trade_service.add_take_profit(
            order=buy_order, percentage=5, trailing=False,
            sell_percentage=100, mirror_on_exchange=True,
        )
        order_service.update(
            buy_order.id,
            {"filled": 20, "remaining": 0, "status": OrderStatus.CLOSED.value}
        )
        return trade_service.find({"order_id": buy_order.id})

    def test_only_one_mirror_order_rests_at_a_time(self):
        trade = self._open_trade_with_both_mirrored()
        stop_loss = trade.stop_losses[0]
        take_profit = trade.take_profits[0]

        # Only the first-placed (stop-loss, since it's processed
        # first) actually gets a resting order -- the take-profit
        # mirror is skipped since it would double-commit the same
        # shares.
        self.assertIsNotNone(stop_loss.mirror_order_id)
        self.assertIsNone(take_profit.mirror_order_id)

    def test_mirror_fill_cancels_sibling_mirror_order(self):
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()
        order_repository = self.app.container.order_repository()

        trade = self._open_trade_with_both_mirrored()
        stop_loss = trade.stop_losses[0]
        mirror_order = order_repository.get(stop_loss.mirror_order_id)

        # Simulate the resting mirror stop-loss order filling on the
        # exchange (bot was "down" -- detected via the normal poll).
        order_service.update(
            mirror_order.id,
            {
                "filled": 20, "remaining": 0,
                "status": OrderStatus.CLOSED.value
            }
        )

        trade = trade_service.get(trade.id)
        self.assertEqual(TradeStatus.CLOSED.value, trade.status)
        stop_loss = trade_service.trade_stop_loss_repository.get(
            stop_loss.id
        )
        self.assertTrue(stop_loss.mirror_triggered)

        # The take-profit never got a resting order in the first
        # place (previous test), so there's nothing left to orphan --
        # this just confirms cleanup runs without error even when
        # there's no sibling order to cancel.
        take_profit = trade_service.trade_take_profit_repository.get(
            trade.take_profits[0].id
        )
        self.assertIsNone(take_profit.mirror_order_id)

    def test_mirror_fill_cancels_sibling_mirror_order_when_both_rest(self):
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()
        order_repository = self.app.container.order_repository()

        buy_order = order_service.create({
            "target_symbol": "ADA",
            "trading_symbol": "EUR",
            "amount": 20,
            "order_side": "BUY",
            "price": 10,
            "order_type": "LIMIT",
            "portfolio_id": 1,
        })
        # 50% each -- both fit within the trade's available amount at
        # once, so both mirror orders actually get placed.
        trade_service.add_stop_loss(
            order=buy_order, percentage=10, trailing=False,
            sell_percentage=50, mirror_on_exchange=True,
        )
        trade_service.add_take_profit(
            order=buy_order, percentage=5, trailing=False,
            sell_percentage=50, mirror_on_exchange=True,
        )
        order_service.update(
            buy_order.id,
            {"filled": 20, "remaining": 0, "status": OrderStatus.CLOSED.value}
        )
        trade = trade_service.find({"order_id": buy_order.id})
        stop_loss = trade.stop_losses[0]
        take_profit = trade.take_profits[0]
        self.assertIsNotNone(stop_loss.mirror_order_id)
        self.assertIsNotNone(take_profit.mirror_order_id)

        tp_mirror_order = order_repository.get(take_profit.mirror_order_id)
        self.assertEqual(OrderStatus.OPEN.value, tp_mirror_order.status)

        # Simulate the stop-loss's resting mirror order filling.
        sl_mirror_order = order_repository.get(stop_loss.mirror_order_id)
        order_service.update(
            sl_mirror_order.id,
            {
                "filled": 10, "remaining": 0,
                "status": OrderStatus.CLOSED.value
            }
        )

        # The take-profit's still-resting mirror order must now be
        # cancelled -- it's stale, the trade portion it targeted may
        # already be gone.
        tp_mirror_order = order_repository.get(take_profit.mirror_order_id)
        self.assertEqual(OrderStatus.CANCELED.value, tp_mirror_order.status)
