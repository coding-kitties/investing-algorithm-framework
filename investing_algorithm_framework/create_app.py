import logging
from dotenv import load_dotenv

from .app import App
from .dependency_container import setup_dependency_container

logger = logging.getLogger("investing_algorithm_framework")


def create_app(
    config: dict = None,
    web=False,
    state_handler=None
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

    app = App(web=web, state_handler=state_handler)
    app = setup_dependency_container(
        app,
        ["investing_algorithm_framework"],
        ["investing_algorithm_framework"]
    )
    # After the container is setup, initialize the services
    app.initialize_services()

    if config is not None:
        app.set_config_with_dict(config)

    logger.info("Investing algoritm framework app created")
    return app
