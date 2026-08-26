from fastapi import FastAPI

from investing_algorithm_framework.app.web.controllers import setup_routers
from investing_algorithm_framework.app.web.setup_cors import setup_cors
from .error_handler import setup_error_handler


def create_fastapi_app(configuration_service):
    app = FastAPI(title="Investing Algorithm Framework")

    web_config = configuration_service.get_web_config()
    app = setup_cors(
        app, allow_origins=web_config.get("CORS_ORIGIN_WHITELIST")
    )
    app = setup_routers(app)
    app = setup_error_handler(app)
    return app
