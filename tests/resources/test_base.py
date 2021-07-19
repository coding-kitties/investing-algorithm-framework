import os
from flask_testing import TestCase
from investing_algorithm_framework.configuration.constants import \
    DATABASE_CONFIG, DATABASE_NAME, RESOURCES_DIRECTORY
from investing_algorithm_framework.core.models import db
from investing_algorithm_framework.app import App
from investing_algorithm_framework.configuration.settings import TestConfig
from investing_algorithm_framework.configuration.setup import setup_database


class TestBase(TestCase):
    resources_dir = os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 'databases'
    )
    algo_app = App(resources_directory=resources_dir, config=TestConfig)

    def create_app(self):
        self.algo_app._initialize_flask_app()
        setup_database(self.algo_app._flask_app)
        return self.algo_app._flask_app

    def setUp(self):
        self.algo_app.start_database()
        self.algo_app.start_scheduler()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

        database_directory_path = self.algo_app.config.get(RESOURCES_DIRECTORY)
        database_name = self.algo_app.config.get(DATABASE_CONFIG)\
            .get(DATABASE_NAME)
        database_path = os.path.join(
            database_directory_path,
            "{}.sqlite3".format(database_name)
        )

        if os.path.isfile(database_path):
            os.remove(database_path)
