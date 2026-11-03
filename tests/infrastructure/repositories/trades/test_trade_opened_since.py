from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import patch

import pandas as pd
from sqlalchemy import event, text

from investing_algorithm_framework.app.context import Context
from investing_algorithm_framework.domain import \
    OrderSide, OrderType, TradeStatus
from investing_algorithm_framework.infrastructure.database import Session
from investing_algorithm_framework.infrastructure.models import SQLTrade
from investing_algorithm_framework.infrastructure.repositories.event_memory \
    import event_memory_scope
from investing_algorithm_framework.infrastructure.repositories \
    .order_repository import SQLOrderRepository
from investing_algorithm_framework.infrastructure.repositories \
    .trade_repository import SQLTradeRepository
from investing_algorithm_framework.services.repository_service \
    import RepositoryService
from tests.resources import BitvavoTestBase


def create_history(trades, orders, watermark):
    created = []
    for symbol, opened_at, closed in (
        ("BTC", watermark - timedelta(days=1), True),
        ("BTC", watermark, True),
        ("BTC", watermark + timedelta(hours=1), False),
        ("BTC", None, False),
        ("ETH", watermark + timedelta(hours=1), False),
    ):
        order = orders.create({
            "target_symbol": symbol, "trading_symbol": "EUR",
            "amount": 1., "price": 100., "order_side": OrderSide.BUY,
            "order_type": OrderType.LIMIT,
        })
        created.append(trades.create({
            "buy_order": order, "target_symbol": symbol,
            "trading_symbol": "EUR", "opened_at": opened_at,
            "amount": 1., "filled_amount": 1., "remaining": 0.,
            "available_amount": 0. if closed else 1.,
            "status": TradeStatus.CLOSED.value if closed
            else TradeStatus.OPEN.value,
            "closed_at": watermark + timedelta(hours=1) if closed else None,
        }))
    return created


class TestSQLTradeOpenedSince(BitvavoTestBase):
    def test_context_applies_inclusive_sql_bound_before_loading(self):
        watermark = datetime(2026, 1, 2)
        trades = self.app.container.trade_service()
        created = create_history(
            SQLTradeRepository(), SQLOrderRepository(), watermark,
        )
        statements = []

        def capture(connection, cursor, statement, parameters, context, many):
            statements.append(statement)

        with Session() as session:
            engine = session.get_bind()
        event.listen(engine, "before_cursor_execute", capture)
        try:
            selected = self.app.context.get_trades(
                target_symbol="BTC", trading_symbol="EUR",
                opened_since=watermark,
            )
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        self.assertEqual(
            {trade.id for trade in selected},
            {created[1].id, created[2].id},
        )
        self.assertTrue(any(
            "trades.opened_at >= " in statement for statement in statements
        ))
        with Session() as session:
            plan = session.execute(text(
                "EXPLAIN QUERY PLAN SELECT id FROM trades "
                "WHERE opened_at >= :opened_since"
            ), {"opened_since": watermark}).all()
        self.assertTrue(any("ix_trades_opened_at" in row[-1] for row in plan))
        self.assertEqual(len(trades.get_all({
            "opened_at_gte": watermark, "status": TradeStatus.CLOSED.value,
        })), 1)


class TestArchivedTradeOpenedSince(TestCase):
    def test_pandas_timestamp_bound_remains_a_datetime(self):
        watermark = pd.Timestamp("2026-01-02", tz="UTC")
        trades, orders = SQLTradeRepository(), SQLOrderRepository()
        with event_memory_scope(accounting_backend="python"):
            created = create_history(trades, orders, watermark)
            context = Context.__new__(Context)
            context.trade_service = RepositoryService(trades)
            selected = context.get_trades(
                target_symbol="BTC", trading_symbol="EUR",
                opened_since=watermark,
            )
            self.assertEqual(
                {trade.id for trade in selected},
                {created[1].id, created[2].id},
            )

    def test_range_filters_before_decode_in_python_and_rust(self):
        for backend in ("python", "rust"):
            with self.subTest(backend=backend):
                if backend == "rust":
                    from investing_algorithm_framework.domain.native_event \
                        import load_native_event_accounting
                    try:
                        load_native_event_accounting()
                    except (ImportError, ValueError):
                        continue
                watermark = datetime(2026, 1, 2, tzinfo=timezone.utc)
                trades, orders = SQLTradeRepository(), SQLOrderRepository()
                with event_memory_scope(accounting_backend=backend) as state:
                    created = create_history(trades, orders, watermark)
                    table = state.rows[SQLTrade]
                    table.flush()
                    context = Context.__new__(Context)
                    context.trade_service = RepositoryService(trades)
                    with patch.object(
                        table, "_read", wraps=table._read,
                    ) as decode:
                        selected = context.get_trades(
                            target_symbol="BTC", trading_symbol="EUR",
                            opened_since=watermark,
                        )
                        self.assertEqual(
                            {trade.id for trade in selected},
                            {created[1].id, created[2].id},
                        )
                        self.assertEqual(
                            decode.call_count, 2 if backend == "rust" else 1,
                        )
