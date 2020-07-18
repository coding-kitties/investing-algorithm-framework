import os
from pathlib import Path

PROJECT_NAME = 'test_project'

# Path that initializes the context
CONTEXT_CONFIGURATION = 'test_project.configuration.context'

# Amount of concurrent workers each state can use
MAX_CONCURRENT_WORKERS = 2

# Change this when not in development, feature or hot-fix branch
DEBUG = int(os.environ.get('DEBUG', True))

BASE_DIR = str(Path(__file__).parent.parent)

LOG_FILE_NAME = 'log'

LOG_DIR = '{}/logs'.format(BASE_DIR)

LOG_PATH = "{}/{}.log".format(LOG_DIR, LOG_FILE_NAME)
#
# if not os.path.isdir(LOG_DIR):
#     os.mkdir(LOG_DIR)

if DEBUG:
    logging_level = "DEBUG"
else:
    logging_level = "INFO"

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(levelname)s %(asctime)s - [thread: %(threadName)-4s %(name)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
        },
    },
    'loggers': {
        '': {
            'level': logging_level,
            'handlers': ['console'],
        },
    },
}

DATABASE_CONFIG = {

}