from bot.data.data_provider import DataProvider

from core.resolvers.plugin_collection import PluginCollector


class TestDiscoverPlugin:

    @staticmethod
    def setup():
        pass

    @staticmethod
    def teardown():
        pass

    def test(self):
        collector = PluginCollector(package_name='bot', plugin_class_type=DataProvider)
        collector.load_plugins()

        for plugin in collector.plugins:
            assert isinstance(plugin, DataProvider)
