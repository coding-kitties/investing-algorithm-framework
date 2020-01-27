import os
from abc import ABC, abstractmethod

from bot.core.exceptions import ImproperlyConfigured


class Template:
    """
    A template class is responsible for creating a templates for the bot.
    """

    def __init__(self, bot_project_directory: str, bot_name: str) -> None:

        if bot_project_directory is None:
            raise ImproperlyConfigured("The given project directory is None")

        if not os.path.isdir(bot_project_directory):
            raise ImproperlyConfigured("The given bot project directory for the bot does not exist")

        self._bot_name = bot_name
        self._bot_project_directory = bot_project_directory

    @abstractmethod
    def configure(self) -> None:
        """
        Function will configure and validate a given app directory.
        Do here all you validation before you are going to use the template.
        """
        pass
