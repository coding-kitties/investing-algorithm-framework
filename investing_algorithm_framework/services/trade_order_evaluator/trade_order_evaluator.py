from abc import ABC, abstractmethod
from typing import List, Dict
import polars as pl
from investing_algorithm_framework.domain import Trade, Order


class TradeOrderEvaluator(ABC):

    def __init__(
        self,
        trade_service,
        order_service
    ):
        self.trade_service = trade_service
        self.order_service = order_service

    @abstractmethod
    def evaluate(
        self,
        open_trades: List[Trade],
        open_orders: List[Order],
        ohlcv_data: Dict[str, pl.DataFrame]
    ):
        """
        Evaluate trades and orders based on OHLCV data. This
        function is responsible for updating open orders and open trades.
        The evaluation process includes checking if orders have been executed
        and updating the trades with the latest prices and execution status.
        Additionally, it may trigger stop-loss and take-profit orders
        based on the current market conditions.

        Args:
            open_trades (List[Trade]): List of open Trade objects.
            open_orders (List[Order]): List of open Order objects.
            ohlcv_data (dict[str, pl.DataFrame]): Mapping of
                symbol -> OHLCV Polars DataFrame.

        Returns:
            List[dict]: Updated trades with latest prices and execution status.
        """
        pass
