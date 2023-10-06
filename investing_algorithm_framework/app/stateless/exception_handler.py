import json
import logging
from typing import Dict, List

from investing_algorithm_framework.domain import OperationalException

logger = logging.getLogger("investing_algorithm_framework")


def create_error_response(error_message, status_code: int = 400):
    response = json.dumps({"error_message": error_message})
    return response, status_code


def format_marshmallow_validation_error(errors):
    errors_message = {}

    for key in errors:

        if isinstance(errors[key], Dict):
            errors_message[key] = \
                format_marshmallow_validation_error(errors[key])

        if isinstance(errors[key], List):
            errors_message[key] = errors[key][0].lower()
    return errors_message


def handle_exception(error):
    logger.error("exception of type {} occurred".format(type(error)))
    logger.exception(error)

    if isinstance(error, OperationalException):
        return error.to_response()
    else:
        # Internal error happened that was unknown
        return {
            "status": "error",
            "message": str(error)
        }
