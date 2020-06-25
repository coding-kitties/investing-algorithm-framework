import os
import re
from importlib import import_module

from investing_algorithm_framework.core.exceptions import ImproperlyConfigured
from investing_algorithm_framework.management.command import BaseCommand, \
    CommandError
from investing_algorithm_framework.configuration.setup.\
    default_template_creators import DefaultProjectCreator


class CreateStandardAlgorithmCommand(BaseCommand):
    help = (
        "Creates a project directory structure for the given "
        "investing_algorithm_framework instance in the current "
        "directory or optionally in the given directory."
    )

    missing_args_message = "You must provide a project name."
    success_message = "Algorithm created and initialized."

    def add_arguments(self, parser):
        parser.add_argument('name', help='Name of the algorithm/project.')
        parser.add_argument(
            'directory', nargs='?', help='Optional destination directory'
        )

    def handle(self, **options) -> None:

        # Get all the default attributes
        project_name = options.get('name', None)
        directory = options.get('directory', None)
        template_creator = options.get('template_creator', None)

        self.validate_name(project_name)

        # initialize the investing_algorithm_framework project directory
        if directory is None:
            directory = os.path.join(os.getcwd(), project_name)

            if os.path.isdir(directory):
                raise ImproperlyConfigured(
                    "Directory {} already exists. Please make sure that "
                    "the project name does not correspond to an existing "
                    "directory".format(str(directory))
                )

            os.mkdir(directory)

        else:
            directory = os.path.abspath(os.path.expanduser(directory))

            if not os.path.exists(directory):
                raise CommandError(
                    "Destination directory {} does not exist, please "
                    "create it first.".format(str(directory))
                )

        # Use default investing_algorithm_framework creator
        if not template_creator:
            template_creator = DefaultProjectCreator(directory, project_name)

        # Creates templates
        template_creator.configure()
        template_creator.create()

    @staticmethod
    def validate_name(name: str) -> None:
        """
        Helper function to validate the name of a given project
        """

        if name is None:
            raise CommandError("you must provide a project name")

        if not re.match("^[a-zA-Z_.-]+$", name):
            raise CommandError(
                "{} is not allowed, value must begin with a letter and "
                "only contains the characters of A-Z, "
                "a-z and _".format(name)
            )

        # Make sure it can't be imported
        try:
            import_module(name)
        except ImportError:
            pass
        else:
            raise CommandError(
                "'{}' conflicts with the name of an existing Python "
                "module and cannot be used as a project name. Please try "
                "another name.".format(name)
            )
