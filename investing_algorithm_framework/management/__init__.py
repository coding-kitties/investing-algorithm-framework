import json
import click
import requests


@click.group()
def manager():
    pass


@manager.command()
def start():
    response = requests.get("http://localhost:5000/start")
    if response.status_code == 200:
        print("algorithm started")
    else:
        print("Could not start algorithm")


@manager.command()
def stop():
    response = requests.get("http://localhost:5000/stop")

    if response.status_code == 200:
        print("algorithm stopped")
    else:
        print("Could not stop algorithm")


@manager.command()
def orders():
    response = requests.get("http://localhost:5000/api/orders")

    if response.status_code == 200:
        print(json.dumps(response.json(), indent=4, sort_keys=True))
    else:
        print("Could not retrieve algorithm orders")



@manager.command()
def positions():
    response = requests.get("http://localhost:5000/api/positions")

    if response.status_code == 200:
        print(json.dumps(response.json(), indent=4, sort_keys=True))
    else:
        print("Could not retrieve algorithm positions")



@manager.command()
def portfolio():
    response = requests.get("http://localhost:5000/api/portfolios/default")

    if response.status_code == 200:
        print(json.dumps(response.json(), indent=4, sort_keys=True))
    else:
        print("Could not retrieve portfolio")

