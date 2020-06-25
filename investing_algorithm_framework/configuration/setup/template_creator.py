import os
import stat
from abc import ABC, abstractmethod

from investing_algorithm_framework.configuration.setup.template import Template


class TemplateCreator(Template, ABC):

    rewrite_template_suffixes = (
        # Allow shipping invalid .py files without byte-compilation.
        ('.py-template', '.py'),
    )

    def __init__(self,  bot_project_directory: str, bot_name: str) -> None:
        super(TemplateCreator, self).__init__(bot_project_directory, bot_name)
        self._creation_mode = True

        super(TemplateCreator, self).configure()

    @abstractmethod
    def create(self) -> None:
        """
        Create here the template, it is recommended to first call the configure
        method, this will check if everything is setup correctly.
        """

        pass

    @staticmethod
    def make_writeable(filename):
        """
        Function that will make a file writeable.
        """

        if not os.access(filename, os.W_OK):
            st = os.stat(filename)
            new_permissions = stat.S_IMODE(st.st_mode) | stat.S_IWUSR
            os.chmod(filename, new_permissions)
