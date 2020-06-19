import os
from pathlib import Path

BOT_PROJECT_NAME = 'bot'

BOT_CONTEXT_CONFIGURATION = 'bot.configuration.context'

# Change this when not in development, feature or hot-fix branch
DEBUG = int(os.environ.get('DEBUG', True))

BASE_DIR = str(Path(__file__).parent.parent)

LOG_FILE_NAME = 'log'

LOG_DIR = '{}/logs'.format(BASE_DIR)

LOG_PATH = "{}/{}.log".format(LOG_DIR, LOG_FILE_NAME)

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