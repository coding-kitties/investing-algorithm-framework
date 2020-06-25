import os
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Query, class_mapper, sessionmaker, scoped_session, \
    Session
from sqlalchemy.orm.exc import UnmappedClassError
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm.exc import DetachedInstanceError
from sqlalchemy.exc import DatabaseError

from investing_algorithm_framework.configuration import settings
from investing_algorithm_framework.configuration.config_constants import \
    BASE_DIR, DATABASE_NAME
from investing_algorithm_framework.core.exceptions import \
    DatabaseOperationalException


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
    table_name = None
    session = None
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


class DatabaseResolver:

    def __init__(self, query_class=Query, model_class=Model):
        self._configured = False
        self.Query = query_class
        self._model = self.make_declarative_base(model_class)
        self.engine = None
        self.session_factory = None
        self.Session = None
        self.database_path = None

    def configure(self):
        self.initialize()
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)

        if self._model is None:
            raise DatabaseOperationalException("Model is not defined")

        self._model.session = _SessionProperty(self)

        if not getattr(self._model, 'query_class', None):
            self._model.query_class = self.Query

        self._model.query = _QueryProperty(self)

    def initialize(self):
        base_dir = settings.get(BASE_DIR)
        database_name = settings.get(DATABASE_NAME)

        if database_name is not None:
            self.database_path = os.path.join(
                base_dir, database_name, '.sqlite3'
            )
        else:
            self.database_path = os.path.join(base_dir, 'db.sqlite3')

        # Only create the database if not exist
        if not os.path.isfile(self.database_path):
            os.mknod(self.database_path)

        self.engine = create_engine('sqlite:////{}'.format(self.database_path))

    @staticmethod
    def make_declarative_base(model_class):
        """
        Creates the declarative base that all models will inherit from.
        """

        model = declarative_base(cls=model_class)
        return model

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
