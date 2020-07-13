import os
from enum import Enum
from typing import Any, Dict
from abc import abstractmethod, ABC

from sqlalchemy import create_engine
from sqlalchemy.orm import Query, class_mapper, sessionmaker, scoped_session, \
    Session
from sqlalchemy.orm.exc import UnmappedClassError
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm.exc import DetachedInstanceError
from sqlalchemy.exc import DatabaseError

from investing_algorithm_framework.core.context import Context
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.configuration.config_constants import \
    DATABASE_NAME, DATABASE_CONFIG, DATABASE_TYPE, DATABASE_DIRECTORY_PATH, \
    DATABASE_URL


class DatabaseType(Enum):
    """
    Class TimeUnit: Enum for TimeUnit
    """

    SQLITE3 = 'SQLITE3',

    # Static factory method to convert a string to time_unit
    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            if value.lower() in ('sqlite', 'sqlite3'):
                return DatabaseType.SQLITE3

            else:
                raise OperationalException(
                    'Could not convert value {} to a time_unit'.format(
                        value
                    )
                )

        else:
            raise OperationalException(
                "Could not convert non string value to a time_unit"
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


class Model(object):
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

    def _repr(self, **fields: Any) -> str:
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


class SQLAlchemyDatabaseResolverInterface(ABC):

    @abstractmethod
    def configure(self, **kwargs: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def make_declarative_base(self, model_class):
        pass

    @property
    @abstractmethod
    def session(self) -> Session:
        pass

    @property
    @abstractmethod
    def model(self):
        pass

    @abstractmethod
    def initialize_tables(self) -> None:
        pass


class SQLAlchemyDatabaseResolverAbstract(
    SQLAlchemyDatabaseResolverInterface, ABC
):

    def __init__(
                self,
                query_class=Query,
                model_class=Model,
    ) -> None:
        self._configured = False
        self.Query = query_class
        self.engine = None
        self.session_factory = None
        self.Session = None
        self._model = self.make_declarative_base(model_class)

    def make_declarative_base(self, model_class):
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
    def model(self) -> Model:
        return self._model

    def initialize_tables(self):
        self._model.metadata.create_all(self.engine)


class SQLAlchemyDatabaseResolver(SQLAlchemyDatabaseResolverAbstract):

    def __init__(
            self,
            query_class=Query,
            model_class=Model,
    ) -> None:
        super(SQLAlchemyDatabaseResolver, self).__init__(
            query_class, model_class
        )
        self.config = {}

    def set_sqlite_config(self, config) -> None:

        try:
            self.config[DATABASE_NAME] = config[DATABASE_NAME]
            self.config[DATABASE_DIRECTORY_PATH] = config[
                DATABASE_DIRECTORY_PATH
            ]
            self.config[DATABASE_TYPE] = 'sqlite3'

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
        except Exception:
            raise DatabaseOperationalException(
                "Missing configuration settings for sqlite3. For sqlite3 the "
                "following attributes are needed: DATABASE_DIRECTORY_PATH, "
                "DATABASE_NAME"
            )

    def configure(self) -> None:

        if not self.config[DATABASE_TYPE]:
            raise DatabaseOperationalException(
                "Database type is not specified"
            )

        if DatabaseType.SQLITE3.equals(self.config[DATABASE_TYPE]):
            self.initialize_sqlite3()

        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)

        if self._model is None:
            raise DatabaseOperationalException("Model is not defined")

        self._model.session = _SessionProperty(self)

        if not getattr(self._model, 'query_class', None):
            self._model.query_class = self.Query

        self._model.query = _QueryProperty(self)

    def initialize_sqlite3(self):

        database_path = os.path.join(
            self.config[DATABASE_DIRECTORY_PATH],
            self.config[DATABASE_NAME] + '.sqlite3'
        )

        if not os.path.isfile(database_path):
            os.mknod(database_path)

        database_url = self.config.get(DATABASE_URL)
        self.engine = create_engine(database_url)


class DatabaseResolver(SQLAlchemyDatabaseResolverInterface):
    """
    Adapter of the SQLAlchemyDatabaseResolver, for the context config or
    standard config object.
    """

    def __init__(
            self, query_class=Query, model_class=Model, context: Context = None
    ) -> None:
        self.resolver = SQLAlchemyDatabaseResolver(query_class, model_class)
        self.context = context

    def configure(self, database_config: dict = None) -> None:
        """
        Function to configure the DatabaseResolver.

        If custom database_config object is passed it will take this
        configuration to configure the DatabaseResolver.

        The database_config must have the same form as in with the
        context config:

        {
            DATABASE_TYPE: <database type>,
            DATABASE_NAME: <database name>,
            DATABASE_DIRECTORY_PATH: <DATABASE_DIRECTORY_PATH> (optional)
        }
        """
        configuration = database_config

        if configuration is None:

            if self.context is None:
                raise DatabaseOperationalException(
                    "Context is not configured with DatabaseResolver instance"
                )

            if not self.context.config.configured:
                raise DatabaseOperationalException(
                    "Context config is not configured"
                )

            try:
                configuration = self.context.config[DATABASE_CONFIG]
            except Exception:
                raise DatabaseOperationalException(
                    "Database configuration has no database configuration"
                )

        if configuration is None:
            raise DatabaseOperationalException(
                "Database configuration has no database configuration"
            )
        try:
            database_type = configuration[DATABASE_TYPE]
        except Exception:
            raise DatabaseOperationalException(
                "Database configuration has no database type defined"
            )

        if DatabaseType.SQLITE3.equals(database_type):
            self.resolver.set_sqlite_config(configuration)
        else:
            raise DatabaseOperationalException(
                "Database type {} is not supported by "
                "the DatabaseResolver".format(database_type)
            )

        self.resolver.configure()

    def make_declarative_base(self, model_class):
        self.resolver.make_declarative_base(model_class)

    @property
    def session(self) -> Session:
        return self.resolver.session

    @property
    def model(self):
        return self.resolver.model

    def initialize_tables(self) -> None:
        self.resolver.initialize_tables()
