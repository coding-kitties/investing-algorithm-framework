import logging
from abc import ABC, abstractmethod
from typing import Dict, Any

from pandas import DataFrame


class IStrategy(ABC):


    def __init__(self, config: Dict[str, Any]):
        self._config = config

    def get_strategy_name(self) -> str:
        """
        Return strategy name
        :return:
        """
        return self.__class__.__name__

    @abstractmethod
    def provide_data(self, data_frame: DataFrame, meta_data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_buy_advice(self, data_frame: DataFrame, meta_data: Dict[str, Any]) -> DataFrame:
        pass

    @abstractmethod
    def get_sell_advice(self, data_frame: DataFrame, meta_data: Dict[str, Any]) -> DataFrame:
        pass


class IIndividualStrategy(IStrategy):
    """
    Strategy for single securities, this will allow for independent evaluation.
    :return:
    """

    @abstractmethod
    def analyze_ticker(self, data_frame: DataFrame, meta_data: Dict[str, Any]) -> DataFrame:
        """
        Analyze the financial data from a particular ticker
        :return:
        """
        pass


class IMultipleStrategy(IStrategy):
    """
    Strategy for multiple securities, so they can be analyzed against each other.
    :return:
    """

    @abstractmethod
    def analyze_ticker_set(self, data_frame: DataFrame, meta_data: Dict[str, Any]) -> DataFrame:
        """
        Analyze the financial data from a set of tickers
        :return:
        """
        pass

