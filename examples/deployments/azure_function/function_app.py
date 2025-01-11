import logging

import azure.functions as func
# from investing_algorithm_framework import StatelessAction
# from app import app as investing_algorithm_framework_app


import logging
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
        },
        'file': {
            'class': 'logging.FileHandler',
            'formatter': 'default',
            'filename': 'app_logs.log',
        },
    },
    'loggers': {  # Make sure to add a 'loggers' section
        'investing_algorithm_framework': {  # Define your logger here
            'level': 'INFO',  # Set the desired level
            'handlers': ['console', 'file'],  # Use these handlers
            'propagate': False,  # Prevent logs from propagating to the root logger (optional)
        },
    },
    'root': {  # Optional: Root logger configuration
        'level': 'WARNING',  # Root logger defaults to WARNING
        'handlers': ['console', 'file'],
    },
}

logging.config.dictConfig(LOGGING_CONFIG)
app = func.FunctionApp()

# Change your interval here, e.ge. "0 */1 * * * *" for every minute
# or "0 0 */1 * * *" for every hour or "0 */5 * * * *" for every 5 minutes
# @func.timer_trigger(
#     schedule="0 */5 * * * *",
#     arg_name="myTimer",
#     run_on_startup=False,
#     use_monitor=False
# )
# def app(myTimer: func.TimerRequest) -> None:

#     if myTimer.past_due:
#         logging.info('The timer is past due!')

#     logging.info('Python timer trigger function ran at %s', myTimer.next)
#     investing_algorithm_framework_app.run(
#         payload={"ACTION": StatelessAction.RUN_STRATEGY.value}
#     )

@app.route(route="test", auth_level=func.AuthLevel.ANONYMOUS)
def test(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    name = req.params.get('name')
    # investing_algorithm_framework_app.run(
    #     payload={"ACTION": StatelessAction.RUN_STRATEGY.value}
    # )

    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            name = req_body.get('name')

    if name:
        return func.HttpResponse(f"Hello, {name}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )
