import logging

from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from investing_algorithm_framework.domain import SQLALCHEMY_DATABASE_URI, \
    OperationalException

Session = sessionmaker()
logger = logging.getLogger("investing_algorithm_framework")


class SQLAlchemyAdapter:

    def __init__(self, app):
        self._app = app
        if SQLALCHEMY_DATABASE_URI not in app.config \
                or app.config[SQLALCHEMY_DATABASE_URI] is None:
            raise OperationalException("SQLALCHEMY_DATABASE_URI not set")

        global Session
        engine = create_engine(
            app.config[SQLALCHEMY_DATABASE_URI],
            connect_args={"config": {"TimeZone": "UTC"}},
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
    SQLBaseModel.metadata.create_all(bind=Session().bind)


from sqlalchemy import event
from sqlalchemy.orm import Mapper
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
    # Drop all tables before deleting file
    try:
        engine = create_engine(
            db_uri,
            connect_args={"config": {"TimeZone": "UTC"}},
        )
        inspector = inspect(engine)
        if inspector.get_table_names():
            logger.info("Dropping all tables in backtest database")
            SQLBaseModel.metadata.drop_all(bind=engine)
    except Exception as e:
        logger.error(f"Error dropping tables: {e}")

    # # Clear mappers (if using classical mappings)
    # try:
    #     clear_mappers()
    # except Exception:
    #     pass  # ignore if not needed


@event.listens_for(Mapper, "load")
def attach_utc_timezone_on_load(target, context):
    """
    For each model instance loaded from the database,
    this function will check if one of the following attributes are
    present: created_at, updated_at, closed_at, opened_at, triggered_at.
    If so, it will ensure these datetime attributes are UTC timezone-aware.

    - If timezone-naive: attach UTC directly.
    - If timezone-aware but not UTC: convert to UTC.

    Its documented in the contributing guide (https://coding-kitties.github
    .io/investing-algorithm-framework/Contributing%20Guide/contributing)
    that each datetime attribute should be utc timezone-aware.

    Args:
        target: The model instance being loaded from the database.
        context: The context in which the event is being handled.

    Returns:
        None
    """
    for attr in (
        "created_at", "updated_at", "closed_at", "opened_at", "triggered_at"
    ):
        if hasattr(target, attr):
            dt = getattr(target, attr)
            if dt is not None:
                if dt.tzinfo is None:
                    setattr(target, attr, dt.replace(tzinfo=timezone.utc))
                elif dt.tzinfo is not timezone.utc:
                    # Normalize any tz (including pytz.UTC) to
                    # datetime.timezone.utc for consistency.
                    setattr(
                        target, attr,
                        dt.astimezone(timezone.utc)
                    )
