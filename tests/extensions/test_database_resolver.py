import os
import pytest
from pathlib import Path

from investing_algorithm_framework.extensions import DatabaseResolver
from investing_algorithm_framework.extensions.database_resolver import \
    DatabaseOperationalException
from investing_algorithm_framework.core.context import Context
from tests.resources.utils import random_string

from sqlalchemy import Column, Integer, String

BASE_DIR = str(Path(__file__).parent.parent)


class TestDatabaseResolverConfiguration:

    def test_sqlite_configuration_with_context(self) -> None:
        os.environ.setdefault(
            'INVESTING_ALGORITHM_FRAMEWORK_SETTINGS_MODULE',
            'tests.resources.database_settings'
        )
        context = Context()
        context.config.configure()
        db = DatabaseResolver(context=context)
        db.configure()

        assert os.path.isfile(os.path.join(BASE_DIR, 'test_db.sqlite3'))
        os.remove(os.path.join(BASE_DIR, 'test_db.sqlite3'))

    def test_sqlite_configuration_from_config_object(self) -> None:
        db = DatabaseResolver()
        db.configure({
            'DATABASE_TYPE': 'sqlite3',
            'DATABASE_NAME': 'test_db',
            'DATABASE_DIRECTORY_PATH': BASE_DIR
        })

        assert os.path.isfile(os.path.join(BASE_DIR, 'test_db.sqlite3'))
        os.remove(os.path.join(BASE_DIR, 'test_db.sqlite3'))

    def test_without_database_configuration(self) -> None:
        os.environ.setdefault(
            'INVESTING_ALGORITHM_FRAMEWORK_SETTINGS_MODULE',
            'tests.resources.standard_settings'
        )
        context = Context()
        context.config.configure()
        db = DatabaseResolver()

        with pytest.raises(DatabaseOperationalException) as exc_inf:
            db.configure()
            assert exc_inf == 'Context config has no database configuration'

    def test_without_database_type_configuration(self) -> None:
        os.environ.setdefault(
            'INVESTING_ALGORITHM_FRAMEWORK_SETTINGS_MODULE',
            'tests.resources.database_settings_without_database_type'
        )
        context = Context()
        context.config.configure()
        db = DatabaseResolver(context)

        with pytest.raises(DatabaseOperationalException) as exc_inf:
            db.configure()
            assert exc_inf == 'Context config database configuration has no ' \
                              'database type defined'

        with pytest.raises(DatabaseOperationalException) as exc_inf:
            db.configure(database_config={})
            assert exc_inf == 'Context config database configuration has no ' \
                              'database type defined'


class TestDatabaseResolver:

    db = DatabaseResolver()

    def setup_method(self) -> None:
        self.db.configure({
            'DATABASE_TYPE': 'sqlite3',
            'DATABASE_NAME': 'test_db',
            'DATABASE_DIRECTORY_PATH': BASE_DIR
        })

    class TestModel(db.model):
        id = Column(Integer, primary_key=True)
        name = Column(String)

        def __repr__(self):
            return self.repr(id=self.id, name=self.name)

    def test_creating(self):
        self.db.initialize_tables()
        assert len(self.TestModel.query.all()) == 0

        test_model_one = self.TestModel(name=random_string(10))

        assert len(self.TestModel.query.all()) == 0

        test_model_one.save()

        assert len(self.TestModel.query.all()) == 1

        test_model_two = self.TestModel(name=random_string(10))

        assert len(self.TestModel.query.all()) == 1

        test_model_two.save()

        assert len(self.TestModel.query.all()) == 2
        self.db.session.commit()

    def test_deleting(self) -> None:
        self.db.initialize_tables()
        assert len(self.TestModel.query.all()) == 0

        test_model_one = self.TestModel(name=random_string(10))
        test_model_two = self.TestModel(name=random_string(10))
        test_model_one.save()
        test_model_two.save()

        assert len(self.TestModel.query.all()) == 2

        test_model_two.delete()

        assert len(self.TestModel.query.all()) == 1

        test_model_one.delete()

        assert len(self.TestModel.query.all()) == 0
        self.db.session.commit()

    def test_updating(self) -> None:
        self.db.initialize_tables()
        assert len(self.TestModel.query.all()) == 0

        test_model_one = self.TestModel(name=random_string(10))
        test_model_two = self.TestModel(name=random_string(10))
        test_model_one.save()
        test_model_two.save()

        model_one_name = test_model_two.name
        self.db.session.commit()

        assert len(self.TestModel.query.all()) == 2

        test_model_one.update(name=random_string(10))

        test_model_one.save()

        self.db.session.commit()

        assert model_one_name != test_model_one.name

    def teardown_method(self) -> None:
        os.remove(os.path.join(BASE_DIR, 'test_db.sqlite3'))
