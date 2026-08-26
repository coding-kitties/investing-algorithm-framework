import logging
from decimal import Decimal

from sqlalchemy import create_engine, StaticPool, String
from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker, close_all_sessions
from sqlalchemy import TypeDecorator

from investing_algorithm_framework.domain import SQLALCHEMY_DATABASE_URI, \
    OperationalException

Session = sessionmaker()
logger = logging.getLogger("investing_algorithm_framework")


class SqliteDecimal(TypeDecorator):
    """
    A type that stores Python numeric values as TEXT in SQLite for
    exact precision. This avoids the lossy float conversion that
    occurs with SQLAlchemy's Float/Numeric types on SQLite.

    - On write: converts the value to its full-precision string
      representation via Decimal, then stores as TEXT.
    - On read: returns a Python float for backward compatibility
      with existing arithmetic code.

    The key benefit is lossless **storage**: the TEXT column preserves
    the exact decimal representation. For example, a value like
    12345678901234.567890123456789 is stored as that exact string
    rather than being silently truncated to a 64-bit float.

    Use this instead of Column(Float) for monetary values, balances,
    prices, and amounts where storage precision matters.
    """
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(Decimal(str(value)))
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return float(Decimal(value))
        return None


class SQLAlchemyAdapter:

    def __init__(self, app):
        self._app = app
        if SQLALCHEMY_DATABASE_URI not in app.config \
                or app.config[SQLALCHEMY_DATABASE_URI] is None:
            raise OperationalException("SQLALCHEMY_DATABASE_URI not set")

        global Session
        engine = create_engine(
            app.config[SQLALCHEMY_DATABASE_URI],
            connect_args={'check_same_thread': False},
            poolclass=StaticPool
        )
        Session.configure(bind=engine)


def setup_sqlalchemy(app, throw_exception_if_not_set=True):

    try:
        SQLAlchemyAdapter(app)
    except OperationalException as e:
        if throw_exception_if_not_set:
            raise e

    return app



class SQLBaseModel(DeclarativeBase):
    pass


def create_all_tables():
    bind = Session().bind
    SQLBaseModel.metadata.create_all(bind=bind)
    _apply_forward_only_migrations(bind)


def _apply_forward_only_migrations(bind):
    """
    Tiny idempotent migration helper.

    The framework has no Alembic; new tables come from
    ``metadata.create_all`` but new *columns* on existing tables do not.
    Live customer SQLite files therefore need an in-place ALTER for any
    column we add post-1.0.

    Each entry below is run once per startup, wrapped in try/except so
    a column that already exists or a non-SQLite backend that handles
    the change differently does not break boot.

    Forward-only, additive, never destructive.
    """
    statements = [
        # #433 — short selling support. ``is_short`` defaults to 0 so
        # every existing long trade keeps its semantics.
        "ALTER TABLE trades ADD COLUMN is_short BOOLEAN "
        "NOT NULL DEFAULT 0",
        # #434 phase 3 — SL/TP inversion for short trades. The
        # ``is_short`` flag on stop-loss / take-profit rows tells the
        # trigger logic to flip the price math.
        "ALTER TABLE trade_stop_losses ADD COLUMN is_short BOOLEAN "
        "NOT NULL DEFAULT 0",
        "ALTER TABLE trade_take_profits ADD COLUMN is_short BOOLEAN "
        "NOT NULL DEFAULT 0",
        # Strategy attribution — lets orders/trades be traced back to
        # the strategy that created them (multi-strategy algorithms).
        # NULL for any row created before this column existed.
        "ALTER TABLE orders ADD COLUMN strategy_id VARCHAR",
        "ALTER TABLE trades ADD COLUMN strategy_id VARCHAR",
    ]
    for stmt in statements:
        try:
            with bind.begin() as conn:
                conn.exec_driver_sql(stmt)
        except Exception:
            # Column already exists, table missing, or non-SQLite
            # dialect with different syntax — all benign at boot.
            pass

    _migrate_position_legs(bind, "positions")
    _migrate_position_legs(bind, "position_snapshots")


def _migrate_position_legs(bind, table_name):
    inspector = inspect(bind)
    if table_name not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns(table_name)
    }
    backfills = {
        "long_amount": (
            "CASE WHEN CAST(amount AS REAL) >= 0 "
            "THEN amount ELSE '0' END"
        ),
        "short_amount": (
            "CASE WHEN CAST(amount AS REAL) < 0 "
            "THEN LTRIM(amount, '-') ELSE '0' END"
        ),
        "long_cost": (
            "CASE WHEN CAST(amount AS REAL) >= 0 "
            "THEN LTRIM(cost, '-') ELSE '0' END"
        ),
        "short_cost": (
            "CASE WHEN CAST(amount AS REAL) < 0 "
            "THEN LTRIM(cost, '-') ELSE '0' END"
        ),
    }
    for column, expression in backfills.items():
        if column in existing_columns:
            continue
        try:
            with bind.begin() as conn:
                conn.exec_driver_sql(
                    f"ALTER TABLE {table_name} ADD COLUMN {column} "
                    "VARCHAR NOT NULL DEFAULT '0'"
                )
                conn.exec_driver_sql(
                    f"UPDATE {table_name} SET {column} = {expression}"
                )
        except Exception:
            pass


def teardown_sqlalchemy():
    """
    Dispose the engine and close all sessions to release file locks.
    This is essential on Windows where file locks are mandatory and
    prevent deletion of SQLite database files while connections are open.
    """
    close_all_sessions()
    bind = Session.kw.get("bind")

    if bind is not None:

        # StaticPool._close_connection() is a no-op, so
        # engine.dispose() alone won't close the underlying DBAPI
        # connection. Use invalidate() which bypasses the pool's
        # _close_connection and calls dialect.do_close() directly,
        # ensuring the sqlite3 file lock is released on Windows.
        try:
            conn = bind.connect()
            conn.invalidate()
            conn.close()
        except Exception:
            pass

        bind.dispose()

    Session.configure(bind=None)


from sqlalchemy import event
from sqlalchemy.orm import mapper
from datetime import timezone

def clear_db(db_uri):
    """
    Clear the database by dropping all tables.
    This is useful for testing purposes.

    Args:
        db_uri (str): The database URI to connect to.

    Returns:
        None
    """
    engine = None
    # Drop all tables before deleting file
    try:
        engine = create_engine(db_uri)
        inspector = inspect(engine)
        if inspector.get_table_names():
            logger.info("Dropping all tables in backtest database")
            SQLBaseModel.metadata.drop_all(bind=engine)
    except Exception as e:
        logger.error(f"Error dropping tables: {e}")
    finally:
        if engine is not None:
            engine.dispose()


@event.listens_for(mapper, "load")
def attach_utc_timezone_on_load(target, context):
    """
    For each model instance loaded from the database,
    this function will check if one of the following attributes are
    present: created_at, updated_at, closed_at, opened_at, triggered_at.
    If so, it will check if these datetime
    attributes are timezone-naive and, if so, will set them to UTC.

    Its documented in the contributing guide (https://coding-kitties.github
    .io/investing-algorithm-framework/Contributing%20Guide/contributing)
    that each datetime attribute should be utc timezone-aware.

    Args:
        target: The model instance being loaded from the database.
        context: The context in which the event is being handled.

    Returns:
        None
    """
    # This will apply to every model instance loaded from the DB
    if hasattr(target, "created_at"):
        dt = getattr(target, "created_at")
        if dt and dt.tzinfo is None:
            target.created_at = dt.replace(tzinfo=timezone.utc)

    if hasattr(target, "updated_at"):
        dt = getattr(target, "updated_at")
        if dt and dt.tzinfo is None:
            target.updated_at = dt.replace(tzinfo=timezone.utc)

    if hasattr(target, "closed_at"):
        dt = getattr(target, "closed_at")
        if dt and dt.tzinfo is None:
            target.closed_at = dt.replace(tzinfo=timezone.utc)

    if hasattr(target, "opened_at"):
        dt = getattr(target, "opened_at")
        if dt and dt.tzinfo is None:
            target.opened_at = dt.replace(tzinfo=timezone.utc)

    if hasattr(target, "triggered_at"):
        dt = getattr(target, "triggered_at")
        if dt and dt.tzinfo is None:
            target.triggered_at = dt.replace(tzinfo=timezone.utc)
