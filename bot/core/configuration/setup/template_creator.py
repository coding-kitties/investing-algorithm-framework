from abc import ABC, abstractmethod

from investing_bot_framework.core.configuration import Template


class TemplateCreator(Template, ABC):

    def __init__(self, _bot_project_directory: str, bot_name: str) -> None:
        super(TemplateCreator, self).__init__(_bot_project_directory, bot_name)
        self._creation_mode = True

    @abstractmethod
    def create(self) -> None:
        """
        Create here the template, it is recommended to first call the configure method, this will check if
        everything is setup correctly.
        """

        pass

