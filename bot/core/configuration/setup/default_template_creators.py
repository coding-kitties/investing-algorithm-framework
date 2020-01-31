import os
import bot
from shutil import copyfile, copymode

from bot.core.exceptions import ImproperlyConfigured
from bot.core.configuration.setup.template_creator import TemplateCreator


class DefaultBotProjectCreator(TemplateCreator):
    TEMPLATE_ROOT_DIR = 'templates/bot_project_template'

    def configure(self) -> None:
        bot_dir = os.path.join(self._bot_project_directory)

        if os.path.exists(bot_dir):
            raise ImproperlyConfigured("Bot destination directory {} already exists".format(self._bot_name))

    def create(self) -> None:

        # Find the default template directory
        template_dir = os.path.join(bot.__path__[0], self.TEMPLATE_ROOT_DIR)

        for root, dirs, files in os.walk(template_dir):

            # Get the last part of the path
            # /home/test_user/bots/investing-bot/bot/templates/configuration ->  configuration
            # This is used as the basis for the copying
            path_rest = root[len(template_dir) + 1:]

            # Create the directories if they don't exist
            destination_dir = os.path.join(self._bot_project_directory, path_rest)
            os.makedirs(destination_dir, exist_ok=True)

            for dirname in dirs[:]:

                if dirname.startswith('.') or dirname == '__pycache__':
                    dirs.remove(dirname)

            for filename in files:

                if filename.endswith(('.pyo', '.pyc', '.py.class')):
                    # Ignore some files as they cause various breakages.
                    continue

                template_path = os.path.join(root, filename)
                destination_path = os.path.join(
                    destination_dir, filename
                )

                for old_suffix, new_suffix in self.rewrite_template_suffixes:

                    if destination_path.endswith(old_suffix):
                        destination_path = destination_path[:-len(old_suffix)] + new_suffix
                        break  # Only rewrite once

                if os.path.exists(destination_path):
                    raise ImproperlyConfigured (
                        "{} already exists. Overlaying {} {} into an existing "
                        "directory won't replace conflicting "
                        "files.".format(destination_path, filename, destination_path)
                    )

                copyfile(template_path, destination_path)

                try:
                    copymode(template_path, destination_path)
                    self.make_writeable(destination_path)
                except OSError:
                    raise ImproperlyConfigured(
                        "Notice: Couldn't set permission bits on {}. You're "
                        "probably using an uncommon filesystem setup.".format(destination_path)
                    )

