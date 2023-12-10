from .app import app
import azure.functions as func
from investing_algorithm_framework import StatelessAction


def main(mytimer: func.TimerRequest) -> None:
    return app.run(payload={"ACTION": StatelessAction.PING})
