from flask import Flask

from investing_algorithm_framework.app.web.controllers import setup_blueprints
from investing_algorithm_framework.app.web.setup_cors import setup_cors
from .error_handler import setup_error_handler


def create_flask_app(config):
    app = Flask(__name__.split('.')[0])

    for key, value in config.items():
        app.config[key] = value

    app = setup_cors(app)
    app.strict_slashes = False
    app = setup_blueprints(app)
    app = setup_error_handler(app)
    return app
