import logging
from datetime import datetime
from collections import namedtuple
from typing import Dict, Type, Any, List

from investing_bot_framework.data import DataProvider
from investing_bot_framework.constants import TimeUnit
from investing_bot_framework import OperationalException
from investing_bot_framework.context.bot_state import BotState
from investing_bot_framework.utils import Singleton, DataSource


ExecutionTask = namedtuple('ExecutionTask', 'time_unit interval last_run')

logger = logging.getLogger(__name__)


class ExecutionScheduler:
    """
    Class Scheduler: This is a lazy scheduler, it will schedule appointments. It only runs it's scheduling algorithm
    when it is asked to. It will then evaluate all the time units and intervals and decide which appointment it needs
    to return.
    """

    def __init__(self):
        self._planning: Dict[str, ExecutionTask] = {}

    def add_execution_task(self, execution_id: str, time_unit: TimeUnit, interval: int = None) -> None:
        """
        Function that will add an appointment to the scheduler
        """

        if execution_id not in self._planning:

            if time_unit is not TimeUnit.ALWAYS and interval is None:
                raise OperationalException("Appoint must set an interval with the corresponding time unit")

            self._planning[execution_id] = ExecutionTask(time_unit=time_unit, interval=interval, last_run=None)

        else:
            raise OperationalException("Can't add appointment, appointment id is already taken")

    def schedule_executions(self) -> List[str]:
        """
        Function that will return all appointments that have hit their time threshold
        """
        appointments: List[str] = []

        for appointment_id in self._planning:

            if self._planning[appointment_id].last_run is None:
                appointments.append(appointment_id)

            elif self._planning[appointment_id].time_unit is TimeUnit.ALWAYS:
                appointments.append(appointment_id)

            else:
                now = datetime.now()

                if self._planning[appointment_id].time_unit is TimeUnit.SECOND:
                    last_run = self._planning[appointment_id].last_run
                    elapsed_time = now - last_run
                    seconds = elapsed_time.total_seconds()

                    if seconds >= self._planning[appointment_id].interval:
                        appointments.append(appointment_id)

                if self._planning[appointment_id].time_unit is TimeUnit.MINUTE:
                    last_run = self._planning[appointment_id].last_run
                    elapsed_time = now - last_run
                    minutes = divmod(elapsed_time.total_seconds(), 60)

                    if minutes[0] >= self._planning[appointment_id].interval:
                        appointments.append(appointment_id)

                elif self._planning[appointment_id].time_unit is TimeUnit.HOUR:
                    last_run = self._planning[appointment_id].last_run
                    elapsed_time = now - last_run
                    hours = divmod(elapsed_time.total_seconds(), 3600)

                    if hours[0] >= self._planning[appointment_id].interval:
                        appointments.append(appointment_id)

            for appointment in appointments:
                self._planning[appointment] = ExecutionTask(
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
    Data provider related attributes
    """
    _data_providers_scheduler = ExecutionScheduler()
    _data_providers: Dict[str, DataProvider] = {}

    """
    The data sources for the investing_bot_framework
    """
    _data_sources: List[DataSource] = None

    def __init__(self) -> None:
        self._config = None

    def initialize(self, bot_state: Type[BotState]) -> None:

        if self._state:
            self._state.stop()

        self._state = bot_state(self)

    def transition_to(self, state: Type[BotState]) -> None:
        """
        The Context allows changing the State object at runtime.
        """

        logger.info("Bot context: Transition to {}".format(state.__name__))
        self._state = state(context=self)

    @property
    def config(self) -> Dict[str, Any]:

        if not self._config:
            raise OperationalException("Config is not specified in the context")

        return self._config

    @config.setter
    def config(self, config: Dict[str, Any]) -> None:
        self._config = config

    @property
    def data_sources(self) -> List[DataSource]:
        return self._data_sources

    @data_sources.setter
    def data_sources(self, data_sources: List[DataSource]) -> None:
        self._data_sources = data_sources

    def add_data_provider(self, data_provider: DataProvider, time_unit: TimeUnit, interval: int = None):
        """
        Function to add a data provider to the investing_bot_framework context
        """
        self._data_providers[data_provider.get_id()] = data_provider
        self._data_providers_scheduler.add_execution_task(data_provider.get_id(), time_unit, interval)

    def get_scheduled_data_providers(self) -> List[DataProvider]:
        data_providers = []
        executions = self._data_providers_scheduler.schedule_executions()

        for data_provider_id in executions:
            data_providers.append(self._data_providers[data_provider_id])

        return data_providers

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
