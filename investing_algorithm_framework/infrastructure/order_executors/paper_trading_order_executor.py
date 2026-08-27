from logging import getLogger

import ccxt

from investing_algorithm_framework.domain import OrderExecutor, \
    OrderStatus, Order, OperationalException, random_string

logger = getLogger("investing_algorithm_framework")

# Cache of ccxt market metadata per exchange id, populated lazily by
# resolve_ccxt_taker_fee_percentage(). Avoids calling load_markets()
# more than once per exchange for the lifetime of the process.
_ccxt_markets_cache = {}


def resolve_ccxt_taker_fee_percentage(market, symbol):
    """
    Best-effort lookup of the exchange's publicly advertised taker fee
    for ``symbol`` on ``market`` (e.g. "BTC/EUR" on "bitvavo"), via
    ccxt's ``load_markets()``. No credentials are required for this —
    it's public market metadata, not an authenticated call.

    Returns the fee as a percentage (e.g. ``0.25`` for 0.25%), or
    ``None`` if it can't be determined for any reason (unsupported
    exchange id, network error, symbol not listed, no fee info) —
    callers should treat ``None`` as "unknown" and fall back to a
    zero/explicitly configured cost instead of raising.
    """
    market_key = market.lower()

    if market_key not in _ccxt_markets_cache:
        try:
            exchange_class = getattr(ccxt, market_key)
            exchange = exchange_class()
            _ccxt_markets_cache[market_key] = exchange.load_markets()
        except Exception as e:
            logger.debug(
                f"Could not load ccxt markets for '{market}' to "
                f"resolve a paper-trading fee estimate: {e}"
            )
            _ccxt_markets_cache[market_key] = None

    markets = _ccxt_markets_cache[market_key]

    if not markets or symbol not in markets:
        return None

    taker = markets[symbol].get("taker")
    return taker * 100 if taker is not None else None


def resolve_ccxt_default_fee_percentages(market):
    """
    Return the exchange's default (lowest-tier) taker/maker fee
    percentages for ``market`` (e.g. "bitvavo"), without any network
    call — this reads ccxt's static ``describe()``/``fees`` metadata,
    not the live, symbol-specific fee schedule from ``load_markets()``.

    Returns:
        tuple[float | None, float | None]: ``(taker_percentage,
        maker_percentage)``, each as a percentage (e.g. ``0.25`` for
        0.25%), or ``(None, None)`` if the exchange id is unknown or
        exposes no default fee metadata.
    """
    market_key = market.lower()

    try:
        exchange_class = getattr(ccxt, market_key)
        exchange = exchange_class()
    except Exception as e:
        logger.debug(
            f"Could not resolve ccxt exchange '{market}' to read its "
            f"default fee schedule: {e}"
        )
        return None, None

    trading_fees = getattr(exchange, "fees", {}).get("trading", {}) or {}
    taker = trading_fees.get("taker")
    maker = trading_fees.get("maker")
    return (
        taker * 100 if taker is not None else None,
        maker * 100 if maker is not None else None,
    )


class PaperTradingOrderExecutor(OrderExecutor):
    """
    Broker-agnostic paper-trading executor (see
    ``PaperTradingMode.LOCAL``/``AUTO`` fallback). No network calls are
    made to place, query, or cancel orders — but resolving a realistic
    fee estimate does make a one-time, unauthenticated ``load_markets()``
    call per exchange (cached), since that's public exchange metadata
    rather than an order operation.

    Orders are left ``OPEN`` (not instant-filled) so the event loop's
    ``DefaultTradeOrderEvaluator`` can validate execution against OHLCV
    data the same way ``BacktestTradeOrderEvaluator`` does for
    backtests — a LIMIT/STOP order only fills once the market actually
    trades through its price, and a MARKET order fills at the open of
    the next available candle.

    Scoped to the specific market(s) it was registered for so it never
    shadows a real ``OrderExecutor`` for a live-traded market in the
    same app.
    """

    def __init__(self, markets, priority=0):
        super().__init__(priority=priority)
        self._markets = {market.upper() for market in markets}

    def supports_market(self, market) -> bool:
        return market.upper() in self._markets

    def execute_order(self, portfolio, order, market_credential) -> Order:
        try:
            order.external_id = f"paper-{random_string(16)}"
            order.filled = 0
            order.remaining = order.amount
            order.status = OrderStatus.OPEN.value
            return order
        except Exception as e:
            logger.exception(e)
            order.status = OrderStatus.REJECTED.value
            return order

    def cancel_order(self, portfolio, order, market_credential) -> Order:
        if OrderStatus.CLOSED.equals(order.status):
            raise OperationalException(
                "Cannot cancel a paper order that has already filled"
            )

        order.status = OrderStatus.CANCELED.value
        return order
