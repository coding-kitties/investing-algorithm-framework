import pathlib

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    SYMBOLS

config = {
    SYMBOLS: ["BTC/EUR"],
    RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()
}
app = create_app(config=config)

