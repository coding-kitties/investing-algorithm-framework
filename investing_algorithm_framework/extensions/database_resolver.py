import os
from enum import Enum
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Query, class_mapper, sessionmaker, scoped_session, \
    Session
from sqlalchemy.orm.exc import UnmappedClassError
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm.exc import DetachedInstanceError
from sqlalchemy.exc import DatabaseError

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.configuration.constants import \
    DATABASE_NAME, DATABASE_TYPE, DATABASE_DIRECTORY_PATH, DATABASE_URL


class DatabaseType(Enum):
    """
    Class TimeUnit: Enum for TimeUnit
    """

    SQLITE3 = 'SQLITE3',
    POSTGRESQL = 'POSTGRESQL'

    # Static factory method to convert a string to time_unit
    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            if value.lower() in ('sqlite', 'sqlite3'):
                return DatabaseType.SQLITE3

            elif value.lower() in ('postgresql', 'postgres'):
                return DatabaseType.POSTGRESQL
            else:
                raise OperationalException(
                    'Could not convert value {} to a data base type'.format(
                        value
                    )
                )

        else:
            raise OperationalException(
                "Could not convert non string value to a data base type"
            )

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value
        else:

            try:
                data_base_type = DatabaseType.from_string(other)
                return data_base_type == self
            except OperationalException:
                pass

            return other == self.value


class DatabaseOperationalException(Exception):
    """
    Class DatabaseOperationalException: Exception class indicating a problem
    occurred during usage of the database
    """
    def __init__(self, message) -> None:
        super(DatabaseOperationalException, self).__init__(message)


class _SessionProperty:
    """
    Wrapper for session property of a Model

    To make sure that each thread gets an scoped session, a new scoped
    session is created if a new thread accesses the session property of
    a Model.
    """
    def __init__(self, db):
        self.db = db

    def __get__(self, instance, owner):
        return self.db.session


class _QueryProperty:
    """
    Wrapper for query property of a Model

    This wrapper makes sure that each model gets a Query object with a
    correct session corresponding to its thread.


    """
    def __init__(self, db):
        self.db = db

    def __get__(self, instance, owner):

        try:
            mapper = class_mapper(owner)
            if mapper:
                return owner.query_class(mapper, session=self.db.session)

        except UnmappedClassError:
            return None


class Model:
    """
    Standard SQL alchemy model

    This model is thread safe
    """
    table_name = None
    session = None

    # Needed for query property
    query_class = None
    _query = None

    @property
    def query(self) -> Query:
        return self._query

    @declared_attr
    def __tablename__(cls):

        if cls.table_name is None:
            return cls.__name__.lower()
        return cls.table_name

    def save(self):
        self.session.add(self)
        self._flush()
        return self

    def update(self, **kwargs):

        for attr, value in kwargs.items():
            setattr(self, attr, value)
        return self.save()

    def delete(self):
        self.session.delete(self)
        self._flush()

    def _flush(self):
        try:
            self.session.flush()
        except DatabaseError:
            self.session.rollback()
            raise

    def repr(self, **fields: Any) -> str:
        """
        Helper for __repr__
        """

        field_strings = []
        at_least_one_attached_attribute = False

        for key, field in fields.items():

            try:
                field_strings.append(f'{key}={field!r}')
            except DetachedInstanceError:
                field_strings.append(f'{key}=DetachedInstanceError')
            else:
                at_least_one_attached_attribute = True

        if at_least_one_attached_attribute:
            return f"<{self.__class__.__name__}({','.join(field_strings)})>"

        return f"<{self.__class__.__name__} {id(self)}>"


class SQLAlchemyDatabaseResolver:

    def __init__(self, query_class=Query, model_class=Model) -> None:
        self._configured = False
        self.Query = query_class
        self.engine = None
        self.session_factory = None
        self.Session = None
        self._model = self.make_declarative_base(model_class)
        self.config = {}
        self._configured = False

    @staticmethod
    def make_declarative_base(model_class):
        """
        Creates the declarative base that all models will inherit from.
        """

        return declarative_base(cls=model_class)

    @property
    def session(self) -> Session:
        """
        Returns scoped session of an Session object
        """
        return self.Session()

    @property
    def Model(self):
        return self._model

    def initialize_tables(self):
        self._model.metadata.create_all(self.engine)

    def set_sqlite_config(self, config) -> None:

        try:
            self.config[DATABASE_NAME] = config[DATABASE_NAME]
            self.config[DATABASE_DIRECTORY_PATH] = config[
                DATABASE_DIRECTORY_PATH
            ]
            self.config[DATABASE_TYPE] = DatabaseType.SQLITE3

            if not os.path.isdir(self.config[DATABASE_DIRECTORY_PATH]):
                raise DatabaseOperationalException(
                    "Give sqlite3 destination directory does not exist for "
                    "director path: {}".format(
                        self.config[DATABASE_DIRECTORY_PATH]
                    )
                )

            database_path = os.path.join(
                self.config[DATABASE_DIRECTORY_PATH],
                self.config[DATABASE_NAME] + '.sqlite3'
            )

            self.config[DATABASE_URL] = 'sqlite:////{}'.format(database_path)

            database_path = os.path.join(
                self.config[DATABASE_DIRECTORY_PATH],
                self.config[DATABASE_NAME] + '.sqlite3'
            )

            if not os.path.isfile(database_path):
                os.mknod(database_path)

            self._configured = True
        except Exception:
            raise DatabaseOperationalException(
                "Missing configuration settings for sqlite3. For sqlite3 the "
                "following attributes are needed: DATABASE_DIRECTORY_PATH, "
                "DATABASE_NAME"
            )

    def set_postgresql_config(self, config) -> None:

        try:
            self.config[DATABASE_URL] = config[DATABASE_URL]
            self.config[DATABASE_TYPE] = DatabaseType.POSTGRESQL
            self._configured = True
        except Exception:
            raise DatabaseOperationalException(
                "Missing configuration settings for postgresql. For "
                "postgresql the following attributes are needed: DATABASE_URL"
            )

    def configure(self, database_config: dict = None) -> None:

        if database_config is None and self.config is None:
            raise DatabaseOperationalException(
                "There is no database configuration"
            )

        if database_config:
            self.config = database_config

            try:
                database_type = self.config[DATABASE_TYPE]
            except Exception:
                raise DatabaseOperationalException(
                    "Database type is not specified"
                )

            if DatabaseType.SQLITE3.equals(database_type):
                self.set_sqlite_config(self.config)

            elif DatabaseType.POSTGRESQL.equals(database_type):
                self.set_postgresql_config(self.config)

        if not self.configured:
            raise DatabaseOperationalException(
                "Database resolver is not configured"
            )

        # Create database engine
        database_url = self.config.get(DATABASE_URL)
        self.engine = create_engine(database_url)

        # Initialize Session object
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)

        if self._model is None:
            raise DatabaseOperationalException("Model is not defined")

        self._model.session = _SessionProperty(self)

        if not getattr(self._model, 'query_class', None):
            self._model.query_class = self.Query

        self._model.query = _QueryProperty(self)

    @property
    def configured(self):
        return self._configured

    @property
    def metadata(self):
        return self.Model.metadata
