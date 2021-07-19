import logging

from flask import Blueprint, jsonify

from investing_algorithm_framework.globals import current_app
from investing_algorithm_framework.exceptions import ApiException

logger = logging.getLogger(__name__)
blueprint = Blueprint("operational-views", __name__)


@blueprint.route("/start", methods=["GET"])
def start_algorithm():
    """
    View for starting the algorithm. If the algorithm is already
    running an exception will be thrown. Otherwise all workers
    will be started and the algorithm will be running.
    """

    if current_app.algorithm.running:
        raise ApiException("Algorithm is already running")

    current_app.algorithm.start()
    return jsonify({"message": "Algorithm started"}), 200


@blueprint.route("/stop", methods=["GET"])
def stop_algorithm():
    """
    View for stopping the algorithm. If the algorithm is already
    stopped an exception will be thrown. Otherwise all workers
    will be stopped.
    """

    if not current_app.algorithm.running:
        raise ApiException("Algorithm is already stopped")

    current_app.algorithm.stop()
    return jsonify({"message": "Algorithm stopped"}), 200
