import logging
from dotenv import load_dotenv

from .app import App
from .dependency_container import setup_dependency_container
from .domain import AppMode

logger = logging.getLogger("investing_algorithm_framework")


def create_app(
    config: dict = None,
    state_handler=None,
    web: bool = False,
    name=None
) -> App:
    """
    Factory method to create an app instance.

    Args:
        config (dict): Configuration dictionary
        web (bool): Whether to create a web app
        state_handler (StateHandler): State handler for the app

    Returns:
        App: App instance
    """
    # Load the environment variables
    load_dotenv()

    app = App(state_handler=state_handler)
    app = setup_dependency_container(
        app,
        ["investing_algorithm_framework"],
        ["investing_algorithm_framework"]
    )
    # After the container is setup, initialize the services
    app.initialize_services()
    app.name = name

    if config is not None:
        app.set_config_with_dict(config)

    if web:
        app.set_config("APP_MODE", AppMode.WEB.value)

    logger.info("Investing algoritm framework app created")

    return app
