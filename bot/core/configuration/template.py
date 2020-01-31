from abc import abstractmethod

from bot.core.exceptions import ImproperlyConfigured


class Template:
    """
    A template class is responsible for creating a templates for the bot.
    """

    def __init__(self, bot_project_directory: str, bot_name: str) -> None:
        """
        bot project directory is the root directory of the given bot. The bot_name will be the same as the root project
        directory. For simplicity it is explicitly passed as a parameter
        """

        if bot_project_directory is None:
            raise ImproperlyConfigured("The given project directory is None")

        self._bot_name = bot_name
        self._bot_project_directory = bot_project_directory

    @abstractmethod
    def configure(self) -> None:
        """
        Function will configure and validate a given app directory.
        Do here all you validation before you are going to use the template.
        """
        pass
