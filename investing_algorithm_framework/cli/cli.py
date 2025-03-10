import click
from .intialize_app import command \
    as initialize_app_command


@click.group()
def cli():
    """CLI for Investing Algorithm Framework"""
    pass

@click.command()
@click.option('--web', is_flag=True, help="Initialize with web UI support")
@click.option(
    '--path', default=None, help="Path to directory to initialize the app in"
)
def init(web, path):
    """
    Command-line tool for creating an app skeleton.

    Args:
        web (bool): Flag to create an app skeleton with web UI support.
        path (str): Path to directory to initialize the app in

    Returns:
        None
    """
    initialize_app_command(path=path, web=web)

# Add the init command to the CLI group
cli.add_command(init)
