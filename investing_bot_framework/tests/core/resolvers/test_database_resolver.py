import os
from unittest import TestCase

from investing_bot_framework.core.resolvers import DatabaseResolver
from investing_bot_framework.tests.resources import BaseTestMixin
from investing_bot_framework.core.configuration import settings
from investing_bot_framework.core.extensions import db


class TestDatabaseResolverConfiguration(TestCase, BaseTestMixin):

    def setUp(self) -> None:
        self.initialize_environment()
        self.db_resolver = DatabaseResolver()

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


