import threading
import webbrowser
import uvicorn


from flask import Flask
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from investing_algorithm_framework.app.web.controllers import setup_blueprints
from investing_algorithm_framework.app.web.setup_cors import setup_cors
from .error_handler import setup_error_handler


def create_flask_app(configuration_service):
    app = Flask(__name__.split('.')[0])

    flask_config = configuration_service.get_flask_config()

    for key, value in flask_config.items():
        app.config[key] = value

    app = setup_cors(app)
    app.strict_slashes = False
    app = setup_blueprints(app)
    app = setup_error_handler(app)
    return app


def create_fastapi_app(configuration_service):
    app = FastAPI()

    # Serve React static files
    app.mount(
        "/",
        StaticFiles(directory="my_framework/static", html=True),
        name="static"
    )
    return app
