# Framework constants
FRAMEWORK_NAME = 'FRAMEWORK_NAME'
ENVIRONMENT = "ENVIRONMENT"
STATELESS = "STATELESS"

# Database Constants
DATABASE_CONFIG = 'DATABASE_CONFIG'
DATABASE_NAME = 'DATABASE_NAME'
DATABASE_TYPE = 'DATABASE_TYPE'
DATABASE_DIRECTORY_PATH = 'DATABASE_DIRECTORY_PATH'
DATABASE_DIRECTORY_NAME = 'DATABASE_DIRECTORY_NAME'
DATABASE_URL = 'DATABASE_URL'
DEFAULT_DATABASE_NAME = "database"

SYMBOLS = "SYMBOLS"
APPLICATION_DIRECTORY = "APP_DIR"
RESOURCE_DIRECTORY = "RESOURCE_DIRECTORY"
BACKTEST_DATA_DIRECTORY_NAME = "BACKTEST_DATA_DIRECTORY_NAME"
LOG_LEVEL = 'LOG_LEVEL'
BASE_DIR = 'BASE_DIR'
SQLALCHEMY_DATABASE_URI = 'SQLALCHEMY_DATABASE_URI'
SQLITE_INITIALIZED = "SQLITE_INITIALIZED"
SQLALCHEMY_INITIALIZED = "SQLALCHEMY_INITIALIZED"
RESERVED_BALANCES = "RESERVED_BALANCES"
APP_MODE = "APP_MODE"
BINANCE = "BINANCE"

IDENTIFIER_QUERY_PARAM = "identifier"
TARGET_SYMBOL_QUERY_PARAM = "target_symbol"
TRADING_SYMBOL_QUERY_PARAM = "trading_symbol"
ORDER_SIDE_QUERY_PARAM = "order_size"
STATUS_QUERY_PARAM = "status"
POSITION_SYMBOL_QUERY_PARAM = "position"
SYMBOL_QUERY_PARAM = "symbol"
TIME_FRAME_QUERY_PARAM = "time_frame"

RESERVED_IDENTIFIERS = [
    BINANCE
]

BINANCE_API_KEY = "binance_api_key"
BINANCE_SECRET_KEY = "binance_secret_key"

CHECK_PENDING_ORDERS = "CHECK_PENDING_ORDERS"
RUN_STRATEGY = "RUN_STRATEGY"

# Configuration
TRADING_SYMBOL = "TRADING_SYMBOL"
CCXT_ENABLED = "CCXT_ENABLED"
API_KEY = "API_KEY"
SECRET_KEY = "SECRET_KEY"
MARKET = "MARKET"
TRACK_PORTFOLIO_FROM = "TRACK_PORTFOLIO_FROM"
SQLITE_ENABLED = "SQLITE_ENABLED"
PORTFOLIOS = "PORTFOLIOS"
STRATEGIES = "STRATEGIES"
APPLICATION_CONFIGURED = "APPLICATION_CONFIGURED"
ACTION = "ACTION"
DEFAULT_PER_PAGE_VALUE = 10
DEFAULT_PAGE_VALUE = 1
ITEMIZE = 'itemize'
ITEMIZED = 'itemized'
PAGE = 'page'
PER_PAGE = 'per_page'
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATETIME_FORMAT_BACKTESTING = "%Y-%m-%d-%H-%M"
CCXT_DATETIME_FORMAT_WITH_TIMEZONE = "%Y-%m-%dT%H:%M:%S.%fZ"
CCXT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
BACKTESTING_FLAG = "BACKTESTING"
BACKTESTING_INDEX_DATETIME = "BACKTESTING_INDEX_DATETIME"
BACKTESTING_START_DATE = "BACKTESTING_START_DATE"
BACKTESTING_END_DATE = "BACKTESTING_END_DATE"
BACKTESTING_INITIAL_AMOUNT = "BACKTESTING_INITIAL_AMOUNT"
TICKER_DATA_TYPE = "TICKER"
OHLCV_DATA_TYPE = "OHLCV"
CURRENT_UTC_DATETIME = "CURRENT_UTC_DATETIME"
SNAPSHOT_INTERVAL = "SNAPSHOT_INTERVAL"

# Deployment
AWS_S3_STATE_BUCKET_NAME = "AWS_S3_STATE_BUCKET_NAME"
