from abc import ABC, abstractmethod

from investing_bot_framework.core.configuration.setup.template_creator import TemplateCreator
from investing_bot_framework.core.configuration.setup.default_template_creators import DefaultBotProjectCreator


class TemplateCreatorFactory(ABC):

    def __init__(self, bot_project_directory: str, bot_name: str) -> None:
        self._bot_project_directory = bot_project_directory
        self._bot_name = bot_name

    @abstractmethod
    def create_project_template_creator(self) -> TemplateCreator:
        pass

    @abstractmethod
    def create_settings_template_creator(self) -> TemplateCreator:
        pass

    @abstractmethod
    def create_data_provider_template_creator(self) -> TemplateCreator:
        pass

    @abstractmethod
    def create_strategies_template_creator(self) -> TemplateCreator:
        pass


class DefaultTemplateCreatorFactory(TemplateCreatorFactory):

    def create_project_template_creator(self) -> TemplateCreator:
        creator = DefaultBotProjectCreator(self._bot_project_directory, self._bot_name)
        creator.configure()
        return creator

    def create_settings_template_creator(self) -> TemplateCreator:
        pass

    def create_data_provider_template_creator(self) -> TemplateCreator:
        pass

    def create_strategies_template_creator(self) -> TemplateCreator:
        pass