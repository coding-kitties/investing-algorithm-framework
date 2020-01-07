import logging
from pandas import DataFrame
from datetime import datetime
from collections import namedtuple
from typing import Dict, Type, Any, List

from bot.context.bot_state import BotState
from bot.strategies import StrategyExecutor
from bot.utils import Singleton, DataSource
from bot import OperationalException
from bot.constants import TimeUnit

Appointment = namedtuple('Appointment', 'time_unit interval last_run')

logger = logging.getLogger(__name__)


class Scheduler:
    """
    Class Scheduler: This is a lazy scheduler, it will schedule appointments. It only runs it's scheduling algorithm
    when it is asked to. It will then evaluate all the time units and intervals and decide which appointment it needs
    to return.
    """

    def __init__(self):
        self._planning: Dict[str, Appointment] = {}

    def add_appointment(self, appointment_id: str, time_unit: TimeUnit, interval: int = None) -> None:
        """
        Function that will add an appointment to the scheduler
        """

        if appointment_id not in self._planning:

            if time_unit is not TimeUnit.always and interval is None:
                raise OperationalException("Appoint must set an interval with the corresponding time unit")

            self._planning[appointment_id] = Appointment(time_unit=time_unit, interval=interval, last_run=None)

        else:
            raise OperationalException("Can't add appointment, appointment id is already taken")

    def schedule_appointments(self) -> List[str]:
        """
        Function that will return all appointments that have hit their time threshold
        """
        appointments: List[str] = []

        for appointment_id in self._planning:

            if self._planning[appointment_id].last_run is None:
                appointments.append(appointment_id)

            elif self._planning[appointment_id].time_unit is TimeUnit.always:
                appointments.append(appointment_id)

            else:
                now = datetime.now()

                if self._planning[appointment_id].time_unit is TimeUnit.minute:
                    last_run = self._planning[appointment_id].last_run
                    elapsed_time = now - last_run
                    minutes = divmod(elapsed_time.total_seconds(), 60)

                    if minutes[0] >= self._planning[appointment_id].interval:
                        appointments.append(appointment_id)

                elif self._planning[appointment_id].time_unit is TimeUnit.hour:
                    last_run = self._planning[appointment_id].last_run
                    elapsed_time = now - last_run
                    hours = divmod(elapsed_time.total_seconds(), 3600)

                    if hours[0] >= self._planning[appointment_id].interval:
                        appointments.append(appointment_id)

            for appointment in appointments:
                self._planning[appointment] = Appointment(
                    self._planning[appointment].time_unit,
                    self._planning[appointment].interval,
                    datetime.now()
                )

        return appointments


class BotContext(metaclass=Singleton):
    """
    The Context defines the interface of interest to clients. It also maintains
    a reference to an instance of a State subclass, which represents the current
    state of the Context.
    """

    """
    A reference to the current state of the Bot Context.
    """
    _state: BotState = None

    """
    List of all the buying and selling orders.
    """
    _buy_orders: DataFrame = None
    _sell_orders: DataFrame = None

    """
    The data sources for the bot
    """
    _analyzed_data: DataFrame = None
    _data_sources: List[DataSource] = None

    """
    Strategy executors
    """
    _strategy_executor = None

    """
    Data provider executors
    """
    _data_provider_executor = None
    _data_provider_executor = None

    def __init__(self) -> None:
        self._config = None

    def initialize(self, bot_state: Type[BotState]) -> None:

        if self._state:
            self._state.stop()

        self._state = bot_state()

    def transition_to(self, state: Type[BotState]) -> None:
        """
        The Context allows changing the State object at runtime.
        """

        logger.info("Bot context: Transition to {}".format(state.__name__))
        self._state = state()

    @property
    def config(self) -> Dict[str, Any]:

        if not self._config:
            raise OperationalException("Config is not specified in the context")

        return self._config

    @config.setter
    def config(self, config: Dict[str, Any]) -> None:
        self._config = config

    @property
    def analyzed_data(self) -> DataFrame:
        return self._analyzed_data

    @analyzed_data.setter
    def analyzed_data(self, data_frame: DataFrame) -> None:
        self._analyzed_data = data_frame

    @property
    def data_sources(self) -> List[DataSource]:
        return self._data_sources

    @data_sources.setter
    def data_sources(self, data_sources: List[DataSource]) -> None:
        self._data_sources = data_sources

    @property
    def performance_mode(self) -> bool:
        return self._performance_mode

    @performance_mode.setter
    def performance_mode(self, flag: bool) -> None:
        self._performance_mode = flag

        if flag:
            logger.info("Bot is running in performance mode ...")

    # @property
    # def data_provider_executor(self) -> DataProviderExecutor:
    #
    #     if not self._data_provider_executor:
    #         raise OperationalException("Currently there is no data provider executor defined for the bot context")
    #
    #     return self._data_provider_executor
    #
    # @data_provider_executor.setter
    # def data_provider_executor(self, executor: DataProviderExecutor) -> None:
    #     self._data_provider_executor = executor

    @property
    def strategy_executor(self) -> StrategyExecutor:

        if not self._strategy_executor:
            raise OperationalException("Currently there is no strategy executor defined for the bot context")

        return self._strategy_executor

    @strategy_executor.setter
    def strategy_executor(self, executor: StrategyExecutor) -> None:
        self._strategy_executor = executor

    """
    The BotContext delegates part of its behavior to the current State object.
    """
    def run(self) -> None:

        if self._state:
            self._state.run()
        else:
            raise OperationalException("Bot context doesn't have a state")

    def stop(self) -> None:

        if self._state:
            self._state.stop()
        else:
            raise OperationalException("Bot context doesn't have a state")

    def reconfigure(self) -> None:

        if self._state:
            self._state.reconfigure()
        else:
            raise OperationalException("Bot context doesn't have a state")
