import os
import shutil

from tests.context.setup_state.setup import TEST_DATA_PROVIDERS_PLUGINS_FILE, TEST_SAMPLE_CONFIG_ONE
from tests.resources.data_providers.test_data_providers import SampleDataProviderOne, SampleDataProviderTwo

from bot.configuration import Configuration
from bot.context.setup_state import SetupState
from bot.context import BotContext, ExecutionScheduler
from bot.constants import TEST_DATA_PROVIDER_RESOURCES, TimeUnit


class TestClass:

    @staticmethod
    def setup():
        test_data_providers_file = os.path.join(TEST_DATA_PROVIDER_RESOURCES, 'test_data_providers.py')
        shutil.copy(test_data_providers_file, TEST_DATA_PROVIDERS_PLUGINS_FILE)

    @staticmethod
    def teardown():
        if os.path.isfile(TEST_DATA_PROVIDERS_PLUGINS_FILE):
            os.remove(TEST_DATA_PROVIDERS_PLUGINS_FILE)

    def test(self):
        args = {'config': TEST_SAMPLE_CONFIG_ONE}
        configuration = Configuration.create_config(args)
        context = BotContext()
        context.config = configuration.config
        context.initialize(SetupState)

        # Mirror configuration of the context data providers
        data_providers = {}
        data_provider_one = SampleDataProviderOne()
        data_providers[data_provider_one.get_id()] = data_provider_one
        data_provider_two = SampleDataProviderTwo()
        data_providers[data_provider_two.get_id()] = data_provider_two

        # Mirror configuration of the context data providers scheduler planning
        scheduler = ExecutionScheduler()
        scheduler.add_execution_task(data_provider_one.get_id(), TimeUnit.ALWAYS)
        scheduler.add_execution_task(data_provider_two.get_id(), TimeUnit.MINUTE, 2)

        assert type(context._state) == SetupState

        context._state._initialize_data_providers()

        assert len(context._data_providers) == len(configuration.config.get('data'))

        for data_provider_id in context._data_providers:
            assert data_provider_id in data_providers
            assert context._data_providers[data_provider_id].get_id() == data_providers[data_provider_id].get_id()
            assert scheduler._planning[data_provider_id].time_unit.equals(
                context._data_providers_scheduler._planning[data_provider_id].time_unit
            )
            assert scheduler._planning[data_provider_id].interval \
                   == context._data_providers_scheduler._planning[data_provider_id].interval
