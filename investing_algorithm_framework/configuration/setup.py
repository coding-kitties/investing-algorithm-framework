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
from investing_algorithm_framework.exceptions import ApiException

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_NAME = "database"


def create_app(config_object=None) -> Flask:
    """
    Function to create a Flask app. The app will be based on the \
    given configuration from the client.
    """

    app = Flask(__name__.split('.')[0])
    CORS(app, supports_credentials=True)
    app.url_map.strict_slashes = False

    # Register error handler
    register_error_handlers(app)

    return app


def setup_config(flask_app, config_object):

    # Validate the configuration
    ConfigValidator.validate(config_object)

    for attribute_key in dir(config_object):
        if attribute_key.isupper():
            flask_app.config[attribute_key] = \
                getattr(config_object, attribute_key)


def setup_database(config_object):

    if DATABASE_CONFIG not in config_object:
        database_path = os.path.join(
            config_object[RESOURCES_DIRECTORY],
            '{}.sqlite3'.format(DEFAULT_DATABASE_NAME)
        )
        config_object[SQLALCHEMY_DATABASE_URI] = database_path
    else:
        database_name = DEFAULT_DATABASE_NAME
        database_directory_path = config_object.get(RESOURCES_DIRECTORY)

        if DATABASE_NAME in config_object.get(DATABASE_CONFIG):
            config_database_name = config_object.get(DATABASE_CONFIG)\
                .get(DATABASE_NAME)

            if config_database_name is not None:
                database_name = config_database_name

        if DATABASE_DIRECTORY_PATH in config_object.get(DATABASE_CONFIG):
            config_database_directory_path = config_object.get(DATABASE_CONFIG)\
                .get(DATABASE_DIRECTORY_PATH)

            if config_database_directory_path is not None:
                database_directory_path = config_database_directory_path

        config_object[DATABASE_CONFIG][DATABASE_DIRECTORY_PATH] = \
            database_directory_path
        config_object[DATABASE_CONFIG][DATABASE_NAME] = database_name

        database_path = os.path.join(
            config_object[DATABASE_CONFIG][DATABASE_DIRECTORY_PATH],
            f'{config_object[DATABASE_CONFIG][DATABASE_NAME]}.sqlite3'
        )

    config_object[SQLALCHEMY_DATABASE_URI] = 'sqlite:////{}'.format(database_path)

    # Create the database if it not exist
    if not os.path.isfile(database_path):
        open(database_path, 'w').close()


def setup_logging(log_level):
    pass
    # logging_config = {
    #     'version': 1,
    #     'disable_existing_loggers': True,
    #     'formatters': {
    #         'standard': {
    #             'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    #         },
    #     },
    #     'handlers': {
    #         'console': {
    #             'level': 'INFO',
    #             'formatter': 'standard',
    #             'class': 'logging.StreamHandler',
    #             'stream': 'ext://sys.stdout',  # Default is stderr
    #         },
    #     },
    #     'loggers': {
    #         '': {  # root logger
    #             'handlers': ['console'],
    #             'level': "DEBUG",
    #             'propagate': False
    #         },
    #         'app': {
    #             'handlers': ['console'],
    #             'level': "DEBUG",
    #             'propagate': False
    #         },
    #     }
    # }
    #
    # logging.config.dictConfig(logging_config)


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
