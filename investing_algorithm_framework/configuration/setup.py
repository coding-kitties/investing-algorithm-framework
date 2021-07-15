import os
import logging
import logging.config
import marshmallow.exceptions as marshmallow_exceptions
from typing import Dict, List
from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from investing_algorithm_framework.configuration import ConfigValidator
from investing_algorithm_framework.configuration.constants import \
    DATABASE_CONFIG, DATABASE_DIRECTORY_PATH, DATABASE_NAME, LOG_LEVEL, \
    SQLALCHEMY_DATABASE_URI, RESOURCES_DIRECTORY
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.exceptions import ApiException
from investing_algorithm_framework.views.operational_views import blueprint \
    as operational_views_blueprint

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_NAME = "database"


def create_app(config_object=None) -> Flask:
    """
    Function to create a Flask app. The app will be based on the \
    given configuration from the client.
    """

    if config_object is None:
        raise OperationalException("Config is not set")

    # Setup logging
    app = Flask(__name__.split('.')[0])
    CORS(app, supports_credentials=True)
    app.url_map.strict_slashes = False

    # Load config
    app.config.from_object(config_object)

    # Validate the configuration
    ConfigValidator.validate(app.config)

    # Register blueprints
    register_blueprints(app)

    # Register error handler
    register_error_handlers(app)

    setup_logging(app.config.get(LOG_LEVEL))

    logger.info("Connecting to sqlite")

    # Initialize the database
    setup_database(app)

    return app


def register_blueprints(app):
    app.register_blueprint(operational_views_blueprint)


def setup_database(app):

    if DATABASE_CONFIG not in app.config:
        database_path = os.path.join(
            app.config[RESOURCES_DIRECTORY],
            '{}.sqlite3'.format(DEFAULT_DATABASE_NAME)
        )
        app.config[SQLALCHEMY_DATABASE_URI] = database_path
    else:
        database_name = DEFAULT_DATABASE_NAME
        database_directory_path = app.config.get(RESOURCES_DIRECTORY)

        if DATABASE_NAME in app.config.get(DATABASE_CONFIG):
            database_name = app.config.get(DATABASE_CONFIG).get(DATABASE_NAME)

        if DATABASE_DIRECTORY_PATH in app.config.get(DATABASE_CONFIG):
            database_directory_path = app.config.get(DATABASE_CONFIG)\
                .get(DATABASE_DIRECTORY_PATH)

        database_path = os.path.join(
            database_directory_path, '{}.sqlite3'.format(database_name)
        )

    app.config[SQLALCHEMY_DATABASE_URI] = 'sqlite:////{}'.format(database_path)

    # Create the database if it not exist
    if not os.path.isfile(database_path):
        open(database_path, 'w').close()


def setup_logging(log_level):

    logging_config = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
                'stream': 'ext://sys.stdout',  # Default is stderr
            },
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False
            },
            'app': {
                'handlers': ['console'],
                'level': log_level,
                'propagate': False
            },
        }
    }

    logging.config.dictConfig(logging_config)


def register_error_handlers(app) -> None:
    """
    Function that will register all the specified error handlers for the app
    """

    def create_error_response(error_message, status_code: int = 400):

        # Remove the default 404 not found message if it exists
        if not isinstance(error_message, Dict):
            error_message = error_message.replace("404 Not Found: ", '')

        response = jsonify({"error_message": error_message})
        response.status_code = status_code
        return response

    def format_marshmallow_validation_error(errors: Dict):
        errors_message = {}

        for key in errors:

            if isinstance(errors[key], Dict):
                errors_message[key] = \
                    format_marshmallow_validation_error(errors[key])

            if isinstance(errors[key], List):
                errors_message[key] = errors[key][0].lower()
        return errors_message

    def error_handler(error):
        logger.error("exception of type {} occurred".format(type(error)))
        logger.exception(error)

        if isinstance(error, HTTPException):
            return create_error_response(str(error), error.code)
        elif isinstance(error, ApiException):
            return create_error_response(
                error.error_message, error.status_code
            )
        elif isinstance(error, marshmallow_exceptions.ValidationError):
            error_message = format_marshmallow_validation_error(error.messages)
            return create_error_response(error_message)
        else:
            # Internal error happened that was unknown
            return "Internal server error", 500

    app.errorhandler(Exception)(error_handler)
