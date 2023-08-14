import logging

from .app import App
from .dependency_container import setup_dependency_container

logger = logging.getLogger("investing_algorithm_framework")

def create_app(
    config={},
    stateless=False,
    web=False,
    initialize=True
):
    app = App(config=config, web=web, stateless=stateless)
    app = setup_dependency_container(
        app,
        ["investing_algorithm_framework"],
        ["investing_algorithm_framework"]
    )

    if initialize:
        app.initialize()

    logger.info( "Investing algoritm framework app created")
    return app
