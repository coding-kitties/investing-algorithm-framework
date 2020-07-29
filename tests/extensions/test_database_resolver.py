import os
import pytest
from pathlib import Path
import testing.postgresql

from investing_algorithm_framework.extensions import SQLAlchemyDatabaseResolver
from investing_algorithm_framework.extensions.database_resolver import \
    DatabaseOperationalException
from tests.resources.utils import random_string

from sqlalchemy import Column, Integer, String

BASE_DIR = str(Path(__file__).parent.parent)


class TestDatabaseResolverConfiguration:

    def test_sqlite_configuration(self) -> None:
        db = SQLAlchemyDatabaseResolver()
        db.set_sqlite_config({
            'DATABASE_TYPE': 'sqlite3',
            'DATABASE_NAME': 'test_db',
            'DATABASE_DIRECTORY_PATH': BASE_DIR
        })
        db.configure()

        assert db.configured
        assert os.path.isfile(os.path.join(BASE_DIR, 'test_db.sqlite3'))
        os.remove(os.path.join(BASE_DIR, 'test_db.sqlite3'))

        db = SQLAlchemyDatabaseResolver()
        db.configure({
            'DATABASE_TYPE': 'sqlite3',
            'DATABASE_NAME': 'test_db',
            'DATABASE_DIRECTORY_PATH': BASE_DIR
        })

        assert db.configured
        assert os.path.isfile(os.path.join(BASE_DIR, 'test_db.sqlite3'))
        os.remove(os.path.join(BASE_DIR, 'test_db.sqlite3'))

    def test_postgresql_configuration(self):
        db = SQLAlchemyDatabaseResolver()

        with testing.postgresql.Postgresql() as postgresql:
            db.set_postgresql_config({
                'DATABASE_TYPE': 'postgresql',
                'DATABASE_URL': postgresql.url(),
            })
            db.configure()

        assert db.configured

        db = SQLAlchemyDatabaseResolver()
        db.configure({
            'DATABASE_TYPE': 'postgresql',
            'DATABASE_URL': postgresql.url(),
        })

        assert db.configured

    def test_without_database_configuration(self) -> None:
        db = SQLAlchemyDatabaseResolver()

        with pytest.raises(DatabaseOperationalException) as exc_inf:
            db.configure()
            assert exc_inf == 'Context config has no database configuration'

        db.config = {
            'DATABASE_TYPE': 'sqlite3',
            'DATABASE_NAME': 'test_db',
            'DATABASE_DIRECTORY_PATH': BASE_DIR
        }

        with pytest.raises(DatabaseOperationalException) as exc_inf:
            db.configure()
            assert exc_inf == 'Context config has no database configuration'

    def test_without_database_type_configuration(self) -> None:
        db = SQLAlchemyDatabaseResolver()

        with pytest.raises(DatabaseOperationalException) as exc_inf:
            db.configure({
                'DATABASE_NAME': 'test_db',
                'DATABASE_DIRECTORY_PATH': BASE_DIR
            })

            assert exc_inf == 'Context config database configuration ' \
                              'has no database type defined'

        with pytest.raises(DatabaseOperationalException) as exc_inf:
            db.configure(database_config={})
            assert exc_inf == 'Context config database configuration has no ' \
                              'database type defined'


class TestDatabaseResolver:

    db = SQLAlchemyDatabaseResolver()

    def setup_method(self) -> None:
        self.db.configure({
            'DATABASE_TYPE': 'sqlite3',
            'DATABASE_NAME': 'test_db',
            'DATABASE_DIRECTORY_PATH': BASE_DIR
        })
        self.db.initialize_tables()

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


class TestDatabaseResolverPostgesql:
    db = SQLAlchemyDatabaseResolver()

    def setup_method(self) -> None:
        self.postgresql = testing.postgresql.Postgresql()
        self.db.configure({
            'DATABASE_TYPE': 'postgresql',
            'DATABASE_URL': self.postgresql.url(),
        })
        self.db.initialize_tables()

    class TestModel(db.model):
        id = Column(Integer, primary_key=True)
        name = Column(String)

        def __repr__(self):
            return self.repr(id=self.id, name=self.name)

    def test_creating(self):
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
        self.postgresql.stop()
