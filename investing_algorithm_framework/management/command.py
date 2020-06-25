import os
from typing import Any
from argparse import ArgumentParser
from abc import abstractmethod, ABC


class CommandError(Exception):
    """
    Exception class indicating a problem while executing a management
    command.
    """

    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super(CommandError, self).__init__(message)


class CommandParser(ArgumentParser):
    """
    Customized ArgumentParser class to improve some error messages and prevent
    SystemExit in several occasions, as SystemExit is unacceptable when a
    command is called programmatically.
    """

    def __init__(
            self,
            *,
            missing_args_message=None,
            called_from_command_line=None,
            **kwargs
    ):
        self.missing_args_message = missing_args_message
        self.called_from_command_line = called_from_command_line
        super().__init__(**kwargs)

    def parse_args(self, args=None, namespace=None):
        # Catch missing argument for a better error message

        if self.missing_args_message and not \
                (args or any(not arg.startswith('-') for arg in args)):
            self.error(self.missing_args_message)
        return super().parse_args(args, namespace)

    def error(self, message):
        if self.called_from_command_line:
            super().error(message)
        else:
            raise CommandError("Error: %s" % message)


class BaseCommand(ABC):
    # Metadata about this command.
    help_message = ''
    success_message = ''
    _called_from_command_line = False

    def create_parser(self, program_name, sub_command, **kwargs) \
            -> CommandParser:
        """
        Create and return the ``ArgumentParser`` which will be used to
        parse the arguments to this command.
        """
        parser = CommandParser(
            prog='%s %s' % (os.path.basename(program_name), sub_command),
            description=self.help_message or None,
            missing_args_message=getattr(self, 'missing_args_message', None),
            called_from_command_line=getattr(
                self, '_called_from_command_line', None
            ),
            **kwargs
        )

        self.add_arguments(parser)
        return parser

    @abstractmethod
    def add_arguments(self, parser) -> None:
        """
        Entry point for subclassed commands to add custom arguments.
        """
        pass

    def execute(self, *args, **options) -> Any:
        """
        Try to execute this command.
        """
        response = self.handle(*args, **options)

        if response is None and self.success_message is not None:
            return self.success_message

    @abstractmethod
    def handle(self, *args, **options) -> Any:
        """
        The actual logic of the command. Subclasses must implement
        this method.
        """
        pass

    def run_from_argv(self, argv) -> Any:

        self._called_from_command_line = True
        parser = self.create_parser(argv[0], argv[1])

        options = parser.parse_args(argv[2:])
        cmd_options = vars(options)

        # Move positional args out of options to mimic legacy optparse
        args = cmd_options.pop('args', ())

        return self.execute(*args, **cmd_options)
