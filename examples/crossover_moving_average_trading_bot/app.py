import pathlib

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY

app = create_app(
    config={RESOURCE_DIRECTORY: pathlib.Path(__file__).parent.resolve()}
)

