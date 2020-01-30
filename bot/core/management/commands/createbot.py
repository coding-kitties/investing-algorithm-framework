import os
from importlib import import_module

from bot.core.management.command import BaseCommand, CommandError
from bot.core.configuration.setup import DefaultBotProjectCreator


class CreateBotCommand(BaseCommand):
    help = (
        "Creates a project directory structure for the given bot name in the current directory or optionally "
        "in the given directory."
    )
    missing_args_message = "You must provide a bot name."

    def add_arguments(self, parser):
        parser.add_argument('name', help='Name of the bot.')
        parser.add_argument('directory', nargs='?', help='Optional destination directory')
        parser.add_argument(
            '--template_creator',
            help='Optional template creator plugin, provided by third party libraries'
        )

    def handle(self, **options):
        bot_name = options.get('name', None)
        directory = options.get('directory', None)
        template_creator = options.get('template_creator', None)

        self.validate_name(bot_name)

        # initialize the bot project directory
        if directory is None:
            directory = os.path.join(os.getcwd(), bot_name)

        else:
            directory = os.path.abspath(os.path.expanduser(directory))

            if not os.path.exists(directory):
                raise CommandError("Destination directory {} does not exist, please create it first.".format(directory))

        if not os.path.isdir(directory):

            try:
                os.makedirs(directory)
            except FileExistsError:
                raise CommandError("{} already exists".format(directory))
            except OSError as e:
                raise CommandError(e)

        # Use default bot creator
        if not template_creator:
            bot_template_creator = DefaultBotProjectCreator(directory, bot_name)

        # Creates templates
        bot_template_creator.configure()
        bot_template_creator.create()

    @staticmethod
    def validate_name(name: str) -> bool:
        """
        Helper function to validate the name of a given bot
        """

        if name is None:
            raise CommandError("you must provide a bot name")

        # Make sure it can't be imported
        try:
            import_module(name)
        except ImportError:
            pass
        else:
            raise CommandError(
                "'{}' conflicts with the name of an existing Python "
                "module and cannot be used as a bot name. Please try "
                "another name.".format(name)
            )

        return True
