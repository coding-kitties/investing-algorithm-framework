import os
from flask_testing import TestCase
from investing_algorithm_framework.configuration.constants import \
    DATABASE_CONFIG, DATABASE_NAME, RESOURCES_DIRECTORY
from investing_algorithm_framework.core.models import db
from investing_algorithm_framework.app import App
from investing_algorithm_framework.configuration.settings import TestConfig


class TestBase(TestCase):
    resources_dir = os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 'databases'
    )
    algo_app = None

    SYMBOL_A = "SYMBOL_A"
    SYMBOL_B = "SYMBOL_B"
    SYMBOL_C = "SYMBOL_C"
    SYMBOL_D = "SYMBOL_D"

    def create_app(self):
        self.algo_app = App(
            resources_directory=self.resources_dir, config=TestConfig
        )
        self.algo_app._initialize_flask_app()
        self.algo_app._initialize_blueprints()
        return self.algo_app._flask_app

    def setUp(self):
        self.algo_app._configured = False
        self.algo_app._config = TestConfig
        self.algo_app._initialize_config()
        self.algo_app._initialize_database()
        self.algo_app._initialize_flask_config()
        self.algo_app._initialize_flask_sql_alchemy()
        self.algo_app.algorithm.initialize()
        self.algo_app.start_scheduler()

    def tearDown(self) -> None:
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

        self.algo_app.reset()
