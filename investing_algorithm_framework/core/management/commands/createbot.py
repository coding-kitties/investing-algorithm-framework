import os
import re
from importlib import import_module

from investing_algorithm_framework.core.exceptions import ImproperlyConfigured
from investing_algorithm_framework.core.management.command import BaseCommand, CommandError
from investing_algorithm_framework.core.configuration.setup import DefaultBotProjectCreator


class CreateBotCommand(BaseCommand):
    help = (
        "Creates a project directory structure for the given investing_algorithm_framework name in the current directory or optionally "
        "in the given directory."
    )

    missing_args_message = "You must provide a investing_algorithm_framework name."
    success_message = "Bot created and initialized."

    def add_arguments(self, parser):
        parser.add_argument('name', help='Name of the investing_algorithm_framework.')
        parser.add_argument('directory', nargs='?', help='Optional destination directory')
        parser.add_argument(
            '--template_creator',
            help='Optional template creator plugin, provided by third party libraries'
        )

    def handle(self, **options) -> str:

        # Get all the default attributes
        bot_name = options.get('name', None)
        directory = options.get('directory', None)
        template_creator = options.get('template_creator', None)

        self.validate_name(bot_name)

        # initialize the investing_algorithm_framework project directory
        if directory is None:
            directory = os.path.join(os.getcwd(), bot_name)

            if os.path.isdir(directory):
                raise ImproperlyConfigured(
                    "Directory {} already exists. Please make sure that the investing_algorithm_framework project name does not correspond to "
                    "an existing directory"
                )

            os.mkdir(directory)

        else:
            directory = os.path.abspath(os.path.expanduser(directory))

            if not os.path.exists(directory):
                raise CommandError("Destination directory {} does not exist, please create it first.".format(directory))

        # Use default investing_algorithm_framework creator
        if not template_creator:
            bot_template_creator = DefaultBotProjectCreator(directory, bot_name)

        # Creates templates
        bot_template_creator.configure()
        bot_template_creator.create()

    @staticmethod
    def validate_name(name: str) -> None:
        """
        Helper function to validate the name of a given investing_algorithm_framework
        """

        if name is None:
            raise CommandError("you must provide a investing_algorithm_framework name")

        if not re.match("^[a-zA-Z]+\w*$", name):
            raise CommandError("{} is not allowed, value must begin with a letter and "
                               "only contains the characters of 0-9, A-Z, a-z and _".format(name))

        # Make sure it can't be imported
        try:
            import_module(name)
        except ImportError:
            pass
        else:
            raise CommandError(
                "'{}' conflicts with the name of an existing Python "
                "module and cannot be used as a investing_algorithm_framework name. Please try "
                "another name.".format(name)
            )
