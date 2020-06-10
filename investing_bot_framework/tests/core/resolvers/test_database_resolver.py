import os
from unittest import TestCase
from sqlalchemy import Column, String, Integer

from investing_bot_framework.tests.resources import BaseTestMixin, utils
from investing_bot_framework.core.configuration import settings
from investing_bot_framework.core.extensions import db


class TestModel(db.model):
    id = Column(Integer, primary_key=True)
    name = Column(String())


class TestDatabaseResolverConfiguration(TestCase, BaseTestMixin):

    def setUp(self) -> None:
        self.initialize_environment()

    def test_configuration(self):
        settings.configure()
        db.configure()

        # Check if all properties are configured
        self.assertIsNotNone(db.Session)
        self.assertIsNotNone(db.engine)
        self.assertIsNotNone(db.session_factory)
        self.assertIsNotNone(db.database_path)
        self.assertTrue(os.path.isfile(db.database_path))

    def tearDown(self) -> None:

        if os.path.isfile(db.database_path):
            os.remove(db.database_path)


class TestDatabaseResolverModel(TestCase, BaseTestMixin):

    def setUp(self) -> None:
        self.initialize_environment()
        settings.configure()
        db.configure()
        db.initialize_tables()

    def test(self) -> None:

        model = TestModel(name=utils.random_string(10))
        model.save()
        db.session.commit()
        self.assertEqual(1, len(TestModel.query.all()))

        model = TestModel(name=utils.random_string(10))
        model.save()
        db.session.commit()
        self.assertEqual(2, len(TestModel.query.all()))

    def tearDown(self) -> None:

        if os.path.isfile(db.database_path):
            os.remove(db.database_path)




