import os
import bot
from shutil import copyfile

from bot.core.exceptions import ImproperlyConfigured
from bot.core.configuration.setup.template_creator import TemplateCreator


class DefaultBotProjectCreator(TemplateCreator):

    def configure(self) -> None:
        bot_base_dir = os.path.join(self._bot_project_directory, self._bot_name)

        if os.path.exists(bot_base_dir):
            raise ImproperlyConfigured("Bot base dir {} already exists".format(self._bot_name))

    def create(self) -> None:
        base_sub_dir = os.path.join(self._bot_project_directory, self._bot_name)

        # Create the bot project app directory
        try:
            os.mkdir(base_sub_dir)
        except FileExistsError:
            raise ImproperlyConfigured("{} already exists".format(base_sub_dir))
        except OSError as e:
            raise ImproperlyConfigured(e)

        # Copy manage.py file to bot project directory
        template_dir = os.path.join(bot.__path__[0], 'templates')

        for root, dirs, files in os.walk(template_dir):
            print(root)
            print(dirs)
            print(files)


class DefaultBotAppCreator(TemplateCreator):

    def create(self) -> None:
        settings_file = os.path.join(self._bot_project_directory, 'settings.py')

        if os.path.isfile(settings_file):
            raise ImproperlyConfigured("Settings file already exists")

    def configure(self) -> None:
        pass