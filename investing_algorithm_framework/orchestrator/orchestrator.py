from time import sleep
from typing import List
from threading import Thread

from investing_algorithm_framework.core.data_providers import \
    AbstractDataProvider
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.workers import Worker
from investing_algorithm_framework.core.context import AlgorithmContext


class Orchestrator:
    registered_data_providers: List = None

    def start(self):

        if self.registered_data_providers is None \
                or len(self.registered_data_providers) < 1:
            raise OperationalException(
                "Orchestrator doesn't have any data providers configured."
            )

        for data_provider in self.registered_data_providers:
            context = AlgorithmContext(data_provider)
            worker = Thread(
                name=data_provider.get_id(),
                target=context.start
            )
            worker.setDaemon(True)
            worker.start()

    def stop(self):
        pass

    @staticmethod
    def register_data_providers(
            data_providers: List[AbstractDataProvider]
    ) -> None:

        for data_provider in data_providers:
            assert isinstance(data_provider, AbstractDataProvider), (
                'Data provider must be an instance of the '
                'AbstractDataProvider class'
            )

            assert isinstance(data_provider, Worker), (
                'Data provider must be an instance of the Worker class'
            )

        if Orchestrator.registered_data_providers is None:
            Orchestrator.registered_data_providers = []

    @staticmethod
    def register_data_provider(data_provider: AbstractDataProvider) -> None:

        assert isinstance(data_provider, AbstractDataProvider), (
            'Data provider must be an instance of the '
            'AbstractDataProvider class'
        )

        assert isinstance(data_provider, Worker), (
            'Data provider must be an instance of the Worker class'
        )

        if Orchestrator.registered_data_providers is None:
            Orchestrator.registered_data_providers = []

        Orchestrator.registered_data_providers.append(data_provider)
