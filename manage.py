import click
from yolk.pypi import CheeseShop
from investing_algorithm_framework import get_version

PACKAGE_NAME = 'investing_algorithm_framework'


def get_latest_version_number(package_name):
    pkg, all_versions = CheeseShop().query_versions_pypi(package_name)
    if len(all_versions):
        return all_versions[0]
    return None


@click.group()
def cli():
    pass


@cli.command()
def get_current_pypi_version():
    click.echo(get_latest_version_number(PACKAGE_NAME))


@cli.command()
def get_current_version():
    click.echo(get_version())


@cli.command()
def can_upgrade_pypi():
    current_pypi_version = get_latest_version_number(PACKAGE_NAME)
    current_version = get_version()

    if current_pypi_version is not current_version:
        click.echo(True)
    else:
        click.echo(False)


if __name__ == '__main__':
    cli()
