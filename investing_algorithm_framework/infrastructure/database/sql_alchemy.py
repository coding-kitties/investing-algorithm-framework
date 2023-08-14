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

        if app.config[SQLALCHEMY_DATABASE_URI] != "sqlite:///:memory:":
            engine = create_engine(
                app.config[SQLALCHEMY_DATABASE_URI],
                connect_args={'check_same_thread': False},
                poolclass=StaticPool
            )
        else:
            engine = create_engine(
                app.config[SQLALCHEMY_DATABASE_URI],
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
