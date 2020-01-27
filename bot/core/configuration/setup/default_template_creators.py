import os
import investing_bot_framework
from shutil import copyfile

from investing_bot_framework.core.exceptions import ImproperlyConfigured
from investing_bot_framework.core.configuration.setup.template_creator import TemplateCreator


class DefaultBotProjectCreator(TemplateCreator):

    def configure(self) -> None:
        bot_base_dir = os.path.join(self._app_directory, self._bot_name)

        if os.path.exists(bot_base_dir):
            raise ImproperlyConfigured("Bot base dir {} already exists".format(self._bot_name))

    def create(self) -> None:
        bot_app_dir = os.path.join(self._app_directory, self._bot_name)

        try:
            os.mkdir(bot_app_dir)
        except FileExistsError:
            raise ImproperlyConfigured("{} already exists".format(bot_app_dir))
        except OSError as e:
            raise ImproperlyConfigured(e)

        # Copy manage.py file to bot project directory
        template_dir = os.path.join(investing_bot_framework.__path__[0], 'templates')
        print(template_dir)


class DefaultBotAppCreator(TemplateCreator):

    def create(self) -> None:
        settings_file = os.path.join(self._app_directory, 'settings.py')

        if os.path.isfile(settings_file):
            raise ImproperlyConfigured("Settings file already exists")

    def configure(self) -> None:
        pass