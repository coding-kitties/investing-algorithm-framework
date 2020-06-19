import os
from sqlalchemy import Column, String, Integer

from investing_algorithm_framework.tests.resources import BaseTestMixin, utils
from investing_algorithm_framework.core.configuration import settings
from investing_algorithm_framework.core.extensions import db


class TestModel(db.model):
    id = Column(Integer, primary_key=True)
    name = Column(String())


class TestDatabaseResolverConfiguration(BaseTestMixin):

    def setup_method(self) -> None:
        self.initialize_environment()

    def test_configuration(self):
        settings.configure()
        db.configure()

        # Check if all properties are configured
        assert db.Session is not None
        assert db.engine is not None
        assert db.session_factory is not None
        assert db.database_path is not None
        assert os.path.isfile(db.database_path) == True

    def teardown_method(self) -> None:

        if os.path.isfile(db.database_path):
            os.remove(db.database_path)


class TestDatabaseResolverModel(BaseTestMixin):

    def setup_method(self) -> None:
        self.initialize_environment()
        settings.configure()
        db.configure()
        db.initialize_tables()

    def test(self) -> None:

        model = TestModel(name=utils.random_string(10))
        model.save()
        db.session.commit()
        assert 1 == len(TestModel.query.all())

        model = TestModel(name=utils.random_string(10))
        model.save()
        db.session.commit()
        assert 2 == len(TestModel.query.all())

    def teardown_method(self) -> None:

        if os.path.isfile(db.database_path):
            os.remove(db.database_path)




