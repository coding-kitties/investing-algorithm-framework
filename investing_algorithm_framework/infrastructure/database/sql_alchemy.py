import logging

from sqlalchemy import create_engine, StaticPool
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
    SQLBaseModel.metadata.create_all(bind=Session().bind)


from sqlalchemy import event
from sqlalchemy.orm import mapper
from datetime import timezone


@event.listens_for(mapper, "load")
def attach_utc_timezone_on_load(target, context):
    """
    For each model instance loaded from the database,
    this function will check if the `created_at` and `updated_at`
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
