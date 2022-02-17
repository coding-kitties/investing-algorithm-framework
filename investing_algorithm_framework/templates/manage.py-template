import click

from investing_algorithm_framework import current_app as app


@click.group()
def cli():
    pass


@cli.command()
def start():
    app.start_algorithm()


@cli.command()
def stop():
    app.stop_algorithm()


@cli.command()
def orders():
    print(app.algorithm.get_orders())


@cli.command()
def positions():
    print(app.algorithm.get_positions())


@cli.command()
def portfolio():
    print(app.algorithm.get_portfolio())


if __name__ == '__main__':
    cli()
