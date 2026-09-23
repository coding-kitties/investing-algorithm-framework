import os
import random
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import polars as pl

from investing_algorithm_framework import (
    PortfolioConfiguration,
    MarketCredential,
    OrderStatus,
    TradeStatus,
    BacktestDateRange,
)
from investing_algorithm_framework.domain import INDEX_DATETIME
from investing_algorithm_framework.domain import Order
from investing_algorithm_framework.services import (
    BacktestTradeOrderEvaluator,
    OrderBacktestService,
)
from tests.resources import TestBase

# Path to OHLCV CSV used by these tests (BTC-EUR, 15m, Binance)
OHLCV_CSV = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "resources", "test_data", "ohlcv",
    "OHLCV_BTC-EUR_BINANCE_15m_2023-12-14-21-45_2023-12-25-00-00.csv",
)


class TestNativeEventFills(unittest.TestCase):
    def test_backend_fallback_and_validation(self):
        from investing_algorithm_framework.services.trade_order_evaluator \
            .native import NativeEventFillUnsupported
        target = ('investing_algorithm_framework.services.'
                  'trade_order_evaluator.native.load_native_event_fills')
        arguments = dict(trade_service=MagicMock(), order_service=MagicMock(),
                         trade_stop_loss_service=MagicMock(),
                         trade_take_profit_service=MagicMock())
        for error in (ImportError('not installed'),
                      NativeEventFillUnsupported('wrong version')):
            with patch(target, side_effect=error):
                evaluator = BacktestTradeOrderEvaluator(
                    **arguments, event_fill_backend='auto')
                self.assertIsNone(evaluator._native_fills)
                with self.assertRaises(type(error)):
                    BacktestTradeOrderEvaluator(
                        **arguments, event_fill_backend='rust')
        with patch(target) as loader:
            BacktestTradeOrderEvaluator(**arguments)
            loader.assert_not_called()
        with self.assertRaises(ValueError):
            BacktestTradeOrderEvaluator(
                **arguments, event_fill_backend='invalid')

    def test_stop_limit_trigger_without_fill_and_input_fallback(self):
        from investing_algorithm_framework.services.trade_order_evaluator \
            .native import NativeEventFillUnsupported, load_native_event_fills
        try:
            native = load_native_event_fills()
        except ImportError:
            self.skipTest('Optional native extension is not installed')
        date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        frame = pl.DataFrame({'Datetime': [date], 'Open': [11.0],
                              'Low': [11.0], 'High': [13.0]})
        outcomes = []
        for backend in ('python', 'rust'):
            service = MagicMock()
            evaluator = BacktestTradeOrderEvaluator(
                MagicMock(), MagicMock(), MagicMock(), service,
                event_fill_backend=backend,
            )
            order = Order(id=1, target_symbol='BTC', trading_symbol='EUR',
                          order_type='STOP_LIMIT', order_side='BUY',
                          price=10.0, amount=2.0, updated_at=date,
                          stop_price=12.0)
            evaluator._check_has_executed(order, frame)
            service.update.assert_not_called()
            service.repository.update.assert_called_once_with(
                1, {'triggered_at': date})
            outcomes.append(service.mock_calls)
        self.assertEqual(*outcomes)
        unsupported = frame.with_columns(pl.lit(None).alias('Low'))
        with self.assertRaises(NativeEventFillUnsupported):
            evaluator._check_has_executed(order, unsupported)
        evaluator.event_fill_backend = 'auto'
        with patch('investing_algorithm_framework.services.'
                   'trade_order_evaluator.trade_order_evaluator.'
                   'TradeOrderEvaluator._check_has_executed') as fallback:
            evaluator._check_has_executed(order, unsupported)
            fallback.assert_called_once_with(order, unsupported)
        with self.assertRaises(ValueError):
            native.event_fill_decision([0], [], [1.0], 0, 1, True,
                                       1.0, None, False)

    def test_custom_blotter_partial_fill_and_no_fill_parity(self):
        from investing_algorithm_framework.services.trade_order_evaluator \
            .native import load_native_event_fills
        try:
            load_native_event_fills()
        except ImportError:
            self.skipTest('Optional native extension is not installed')
        date = datetime(2024, 1, 2, tzinfo=timezone.utc)
        frame = pl.DataFrame({'Datetime': [date], 'Open': [10.0],
                              'Low': [9.0], 'High': [11.0], 'Volume': [2.0]})
        for case in ('partial', 'zero', 'empty', 'before_update', 'no_match'):
            with self.subTest(case=case):
                outcomes = []
                for backend in ('python', 'rust'):
                    calls = MagicMock()
                    blotter = calls.blotter
                    blotter.get_fill_price.return_value = 10.25
                    blotter.get_fill_amount.return_value = (
                        0.0 if case == 'zero' else 0.5)
                    blotter.on_fill.return_value = 0.1
                    blotter.get_commission_rate.return_value = 0.01
                    evaluator = BacktestTradeOrderEvaluator(
                        MagicMock(), MagicMock(), MagicMock(), calls.orders,
                        blotter=blotter, event_fill_backend=backend,
                    )
                    order = Order(
                        id=1, target_symbol='BTC', trading_symbol='EUR',
                        order_type='LIMIT', order_side='BUY', amount=2.0,
                        remaining=1.5, filled=0.5, order_fee=0.2,
                        price=8.0 if case == 'no_match' else 10.0,
                        updated_at=(date.replace(day=3)
                                    if case == 'before_update' else date),
                    )
                    evaluator._check_has_executed(
                        order, frame.head(0) if case == 'empty' else frame)
                    if case == 'partial':
                        calls.orders.update.assert_called_once_with(1, {
                            'filled': 1.0, 'remaining': 1.0,
                            'order_fee': 0.2 + 0.1,
                        })
                    else:
                        calls.orders.update.assert_not_called()
                    outcomes.append(calls.mock_calls)
                self.assertEqual(*outcomes)

    def test_exact_decisions_and_fill_updates(self):
        try:
            from investing_algorithm_framework.services.trade_order_evaluator \
                .native import load_native_event_fills
            load_native_event_fills()
        except ImportError:
            self.skipTest('Optional native extension is not installed')
        generator = random.Random(411)
        dates = [datetime(2024, 1, day, tzinfo=timezone.utc)
                 for day in range(1, 21)]
        for kind in ('MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT'):
            for side in ('BUY', 'SELL', 'SHORT', 'COVER'):
                for triggered in (False, True):
                    for volume in (False, True):
                        with self.subTest(kind=kind, side=side,
                                          triggered=triggered, volume=volume):
                            frame = pl.DataFrame({
                                'Datetime': dates,
                                'Open': [10.0] * len(dates),
                                'Low': [generator.uniform(7, 11)
                                        for _ in dates],
                                'High': [generator.uniform(11, 14)
                                         for _ in dates],
                            })
                            frame = frame.with_columns(
                                pl.col('Datetime').cast(
                                    pl.Datetime(
                                        'ns' if volume else 'us', 'UTC')
                                )
                            )
                            if volume:
                                frame = frame.with_columns(pl.lit(20.0)
                                                           .alias('Volume'))
                            outcomes = []
                            for backend in ('python', 'rust'):
                                service = MagicMock()
                                evaluator = BacktestTradeOrderEvaluator(
                                    trade_service=MagicMock(),
                                    trade_stop_loss_service=MagicMock(),
                                    trade_take_profit_service=MagicMock(),
                                    order_service=service,
                                    event_fill_backend=backend,
                                )
                                order = Order(
                                    id=1, target_symbol='BTC',
                                    trading_symbol='EUR', order_type=kind,
                                    order_side=side, price=10.0, amount=2.0,
                                    remaining=2.0, filled=0.0,
                                    updated_at=dates[3], stop_price=12.0,
                                )
                                if triggered:
                                    order.set_triggered_at(dates[2])
                                evaluator._check_has_executed(order, frame)
                                outcomes.append(service.mock_calls)
                            self.assertEqual(outcomes[0], outcomes[1])


class TestBacktestTradeOrderEvaluatorStopLoss(TestBase):
    """
    Integration tests for BacktestTradeOrderEvaluator.evaluate()
    verifying that newly filled orders don't crash stop-loss / take-profit
    evaluation when last_reported_price is None.

    Regression tests for issue #384.
    """

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
            trading_symbol="EUR",
        )
    ]
    external_balances = {"EUR": 1000000}

    def setUp(self):
        super().setUp()

        # Override order service with backtest variant
        self.app.container.order_service.override(
            OrderBacktestService(
                trade_service=self.app.container.trade_service(),
                order_repository=self.app.container.order_repository(),
                position_service=self.app.container.position_service(),
                portfolio_repository=(
                    self.app.container.portfolio_repository()
                ),
                portfolio_configuration_service=(
                    self.app.container.portfolio_configuration_service()
                ),
                portfolio_snapshot_service=(
                    self.app.container.portfolio_snapshot_service()
                ),
                configuration_service=(
                    self.app.container.configuration_service()
                ),
            )
        )

        backtest_date_range = BacktestDateRange(
            start_date=datetime(2023, 12, 14),
            end_date=datetime(2023, 12, 25),
        )
        self.app.initialize_backtest_config(backtest_date_range)

        # Set INDEX_DATETIME before the CSV data starts (first row
        # is 2023-12-14 21:45:00) so that orders are created with
        # updated_at earlier than the OHLCV rows.
        configuration_service = self.app.container.configuration_service()
        configuration_service.add_value(
            INDEX_DATETIME,
            datetime(2023, 12, 14, 21, 0, 0, tzinfo=timezone.utc),
        )

        # Load OHLCV data from local test CSV (no downloads).
        # Convert Datetime to UTC-aware to match the order model's
        # DateTime(timezone=True) column.
        self.ohlcv_df = pl.read_csv(OHLCV_CSV)
        self.ohlcv_df = self.ohlcv_df.with_columns(
            pl.col("Datetime")
            .str.to_datetime()
            .dt.replace_time_zone("UTC")
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _create_evaluator(self):
        return BacktestTradeOrderEvaluator(
            trade_service=self.app.container.trade_service(),
            order_service=self.app.container.order_service(),
            trade_stop_loss_service=(
                self.app.container.trade_stop_loss_service()
            ),
            trade_take_profit_service=(
                self.app.container.trade_take_profit_service()
            ),
            configuration_service=(
                self.app.container.configuration_service()
            ),
        )

    def _create_filled_buy_order(self, target_symbol, price, amount):
        """Create a BUY order and immediately fill it, producing an
        OPEN trade."""
        order_service = self.app.container.order_service()
        order = order_service.create({
            "target_symbol": target_symbol,
            "trading_symbol": "EUR",
            "amount": amount,
            "order_side": "BUY",
            "price": price,
            "order_type": "LIMIT",
            "portfolio_id": 1,
            "status": "CREATED",
        })
        order_service.update(order.id, {
            "status": OrderStatus.CLOSED.value,
            "filled": amount,
            "remaining": 0,
        })
        return order

    def _create_pending_buy_order(self, target_symbol, price, amount):
        """Create a BUY order that stays OPEN (unfilled).  The
        OrderBacktestService.execute_order sets status=OPEN, filled=0."""
        order_service = self.app.container.order_service()
        return order_service.create({
            "target_symbol": target_symbol,
            "trading_symbol": "EUR",
            "amount": amount,
            "order_side": "BUY",
            "price": price,
            "order_type": "LIMIT",
            "portfolio_id": 1,
            "status": "CREATED",
        })

    # ------------------------------------------------------------------
    # tests
    # ------------------------------------------------------------------

    def test_evaluate_no_crash_when_order_fills_with_stop_loss(self):
        """
        Issue #384 — regression test.

        Scenario
        --------
        1. Trade A is already OPEN (previously filled) with a stop-loss.
        2. Order B is OPEN (pending) with a corresponding CREATED trade
           that also has a stop-loss.
        3. evaluate() fills Order B, promoting Trade B to OPEN.
        4. The structural fix re-queries ALL open trades after filling
           orders, so Trade B also gets its price updated.
        5. _check_stop_losses() evaluates ALL OPEN trades without error.
        """
        trade_service = self.app.container.trade_service()
        order_service = self.app.container.order_service()

        # ---- Trade A: already filled → OPEN --------------------------
        order_a = self._create_filled_buy_order("BTC", 39000, 0.1)
        trade_a = trade_service.find({"order_id": order_a.id})
        self.assertEqual(TradeStatus.OPEN.value, trade_a.status)
        trade_service.add_stop_loss(
            trade_a, percentage=10, trailing=False, sell_percentage=50
        )

        # ---- Order B: pending → will fill during evaluate() ----------
        # Price 39200: the CSV Low values start at 39052 which is ≤ 39200
        order_b = self._create_pending_buy_order("BTC", 39200, 0.05)
        # v9.0 (#431) — pending BUY orders have no trade yet; attach
        # the stop-loss to the order so it materializes at fill time.
        trade_service.add_stop_loss(
            order=order_b, percentage=10, trailing=False,
            sell_percentage=50,
        )

        # ---- Prepare evaluate() inputs ------------------------------
        open_trades = trade_service.get_all(
            {"status": TradeStatus.OPEN.value}
        )
        open_orders = order_service.get_all(
            {"status": OrderStatus.OPEN.value}
        )
        self.assertEqual(1, len(open_trades))   # only Trade A
        self.assertEqual(1, len(open_orders))   # only Order B

        # ---- Run evaluate — this must NOT raise TypeError ------------
        evaluator = self._create_evaluator()
        evaluator.evaluate(
            open_trades=open_trades,
            open_orders=open_orders,
            ohlcv_data={"BTC/EUR": self.ohlcv_df},
        )

        # ---- Verify Order B is now filled ----------------------------
        order_b_updated = order_service.get(order_b.id)
        self.assertEqual(OrderStatus.CLOSED.value, order_b_updated.status)

        # ---- Verify Trade B is now OPEN ------------------------------
        trade_b_updated = trade_service.find({"order_id": order_b.id})
        self.assertEqual(TradeStatus.OPEN.value, trade_b_updated.status)

        # The structural fix (#384) re-queries open trades after order
        # fills, so Trade B's price is updated — not left as None.
        self.assertIsNotNone(trade_b_updated.last_reported_price)

        # ---- Verify Trade A also got its price updated ---------------
        trade_a_updated = trade_service.find({"order_id": order_a.id})
        self.assertIsNotNone(trade_a_updated.last_reported_price)

    def test_evaluate_no_crash_when_order_fills_with_take_profit(self):
        """
        Same scenario as above but with take-profit instead of stop-loss.
        """
        trade_service = self.app.container.trade_service()
        order_service = self.app.container.order_service()

        # Trade A: already filled → OPEN
        order_a = self._create_filled_buy_order("BTC", 39000, 0.1)
        trade_a = trade_service.find({"order_id": order_a.id})
        trade_service.add_take_profit(
            trade_a, percentage=10, trailing=False, sell_percentage=50
        )

        # Order B: pending → will fill during evaluate()
        order_b = self._create_pending_buy_order("BTC", 39200, 0.05)
        # v9.0 (#431) — pending BUY orders have no trade yet; attach
        # the take-profit to the order so it materializes at fill time.
        trade_service.add_take_profit(
            order=order_b, percentage=10, trailing=False,
            sell_percentage=50,
        )

        open_trades = trade_service.get_all(
            {"status": TradeStatus.OPEN.value}
        )
        open_orders = order_service.get_all(
            {"status": OrderStatus.OPEN.value}
        )

        evaluator = self._create_evaluator()
        # Must NOT raise TypeError
        evaluator.evaluate(
            open_trades=open_trades,
            open_orders=open_orders,
            ohlcv_data={"BTC/EUR": self.ohlcv_df},
        )

        order_b_updated = order_service.get(order_b.id)
        self.assertEqual(OrderStatus.CLOSED.value, order_b_updated.status)

        trade_b_updated = trade_service.find({"order_id": order_b.id})
        self.assertEqual(TradeStatus.OPEN.value, trade_b_updated.status)
        # Structural fix: newly opened trade also gets its price updated
        self.assertIsNotNone(trade_b_updated.last_reported_price)

    def test_evaluate_only_pending_order_no_existing_open_trades(self):
        """
        Edge case: no existing OPEN trades, only a pending order.
        evaluate() should fill the order without errors.  Because
        open_trades is empty, _check_stop_losses/_check_take_profits
        are skipped entirely (they live inside the
        ``if len(open_trades) > 0`` block).
        """
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()

        order_b = self._create_pending_buy_order("BTC", 39200, 0.05)
        # v9.0 (#431) — attach stop-loss to the pending order so it
        # materializes onto the trade created at fill time.
        trade_service.add_stop_loss(
            order=order_b, percentage=10, trailing=False,
            sell_percentage=50,
        )

        open_trades = trade_service.get_all(
            {"status": TradeStatus.OPEN.value}
        )
        open_orders = order_service.get_all(
            {"status": OrderStatus.OPEN.value}
        )
        self.assertEqual(0, len(open_trades))
        self.assertEqual(1, len(open_orders))

        evaluator = self._create_evaluator()
        evaluator.evaluate(
            open_trades=open_trades,
            open_orders=open_orders,
            ohlcv_data={"BTC/EUR": self.ohlcv_df},
        )

        order_b_updated = order_service.get(order_b.id)
        self.assertEqual(OrderStatus.CLOSED.value, order_b_updated.status)

        trade_b_updated = trade_service.find({"order_id": order_b.id})
        self.assertEqual(TradeStatus.OPEN.value, trade_b_updated.status)
