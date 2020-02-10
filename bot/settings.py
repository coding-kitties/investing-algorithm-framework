import os
import logging.config

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Change this when not in development, feature or hot-fix branch
DEBUG = int(os.environ.get('DEBUG', True))

# Setup logging
# make sure that the log dir exists
log_dir = os.path.abspath(os.path.join(BASE_DIR, 'logs'))
main_log_file = os.path.join(log_dir, 'main.log')

if not os.path.isdir(log_dir):
    os.mkdir(log_dir)

if not os.path.isfile(main_log_file):
    os.mknod(main_log_file)

if DEBUG:
    logging_level = "DEBUG"
else:
    logging_level = "INFO"

logging.config.dictConfig({
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
        'file': {
            'formatter': 'standard',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs/main.log'),
            'backupCount': 10,
            'maxBytes': 10000,
        },
    },
    'loggers': {
        '': {
            'level': logging_level,
            'handlers': ['console', 'file'],
        },
    },
})
