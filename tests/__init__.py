import logging
import warnings

# Suppress noisy loggers during test runs
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("ccxt").setLevel(logging.WARNING)
logging.getLogger("yfinance").setLevel(logging.WARNING)
logging.getLogger("peewee").setLevel(logging.WARNING)
logging.getLogger("investing_algorithm_framework").setLevel(logging.ERROR)

# Suppress ResourceWarning from TemporaryDirectory implicit cleanup
warnings.filterwarnings("ignore", category=ResourceWarning,
                        message="Implicitly cleaning up")

# Suppress DeprecationWarning for 'window_size' parameter
warnings.filterwarnings("ignore", category=DeprecationWarning,
                        message=".*window_size.*deprecated.*")
