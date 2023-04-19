def setup_logging(log_level="INFO"):
    DEFAULT_LOGGING = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
            },
        },
        'handlers': {
            'default': {
                'level': 'INFO',
                'formatter': 'standard',
                'class': 'logging.StreamHandler',
                'stream': 'ext://sys.stdout',  # Default is stderr
            },
        },
        'loggers': {
            '': {  # root logger
                'handlers': ['default'],
                'level': 'WARNING',
                'propagate': False
            },
            'investing_algorithm_framework': {
                'handlers': ['default'],
                'level': 'INFO',
                'propagate': False
            },
            '__main__': {  # if __name__ == '__main__'
                'handlers': ['default'],
                'level': 'DEBUG',
                'propagate': False
            },
        }
    }

    logging.config.dictConfig(DEFAULT_LOGGING)
