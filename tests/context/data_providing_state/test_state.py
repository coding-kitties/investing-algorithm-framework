from tests.resources.data_providers.test_data_providers import SampleDataProviderOne, SampleDataProviderTwo

from bot.constants import TimeUnit
from bot.context import ExecutionScheduler, BotContext
from bot.context.data_providing_state import DataProvidingState


class TestDataProvidingState:

    @staticmethod
    def setup():
        pass

    @staticmethod
    def teardown():
        pass

    def test(self):
        context = BotContext()
        context.initialize(DataProvidingState)

        # Mirror configuration of the context data providers
        data_providers = {}
        data_provider_one = SampleDataProviderOne()
        data_providers[data_provider_one.get_id()] = data_provider_one
        data_provider_two = SampleDataProviderTwo()
        data_providers[data_provider_two.get_id()] = data_provider_two

        context._data_providers = data_providers

        # Mirror configuration of the context data providers scheduler planning
        scheduler = ExecutionScheduler()
        scheduler.add_execution_task(data_provider_one.get_id(), TimeUnit.ALWAYS)
        scheduler.add_execution_task(data_provider_two.get_id(), TimeUnit.MINUTE, 2)

        context._data_providers_scheduler = scheduler

        assert type(context._state) == DataProvidingState

        context._state._initialize()

        # We expect that in the first run all the data providers are scheduled to run
        assert len(context._state._data_provider_executor.registered_data_providers) == 2

        context._state._initialize()

        assert len(context._state._data_provider_executor.registered_data_providers) == 1




