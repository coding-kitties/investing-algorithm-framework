import logging

# Suppress noisy third-party loggers during test runs
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("ccxt").setLevel(logging.WARNING)
