import os
import pytest
from tempfile import TemporaryDirectory
from tests.resources.utils import random_string
from investing_algorithm_framework.management.commands.create_standard_algo \
    import CreateStandardAlgorithmCommand
from investing_algorithm_framework.management.command import CommandError


class TestCreateAlgorithm:
    project_name = None
    project_dir = None

    def setup_method(self):
        self.project_name = random_string(10)

    def test(self):

        with TemporaryDirectory() as tempdir:

            command = CreateStandardAlgorithmCommand()
            command.handle(name=self.project_name, directory=tempdir)

            # Check if manage py is present
            assert os.path.isfile(os.path.join(tempdir, 'manage.py'))

            # Check if all directories are present
            assert os.path.isdir(
                os.path.join(tempdir, self.project_name, 'data_providers')
            )
            assert os.path.isdir(
                os.path.join(tempdir, self.project_name, 'order_executors')
            )
            assert os.path.isdir(
                os.path.join(tempdir, self.project_name, 'strategies')
            )
            assert os.path.isdir(
                os.path.join(tempdir, self.project_name, 'configuration')
            )

            # Check if all configuration files are present
            assert os.path.isfile(
                os.path.join(
                    tempdir,
                    self.project_name,
                    'configuration',
                    '__init__.py')
            )
            assert os.path.isfile(
                os.path.join(
                    tempdir,
                    self.project_name,
                    'configuration',
                    'context.py')
            )
            assert os.path.isfile(
                os.path.join(
                    tempdir,
                    self.project_name,
                    'configuration',
                    'settings.py')
            )
            assert os.path.isfile(
                os.path.join(
                    tempdir,
                    self.project_name,
                    'configuration',
                    'extensions.py')
            )

            # Check if all data provider files are present
            assert os.path.isfile(
                os.path.join(
                    tempdir,
                    self.project_name,
                    'data_providers',
                    '__init__.py')
            )
            assert os.path.isfile(
                os.path.join(
                    tempdir,
                    self.project_name,
                    'data_providers',
                    'data_providers.py')
            )

            # Check if all strategies files are present
            assert os.path.isfile(
                os.path.join(
                    tempdir,
                    self.project_name,
                    'strategies',
                    '__init__.py')
            )
            assert os.path.isfile(
                os.path.join(
                    tempdir,
                    self.project_name,
                    'strategies',
                    'strategies.py'
                )
            )

            # Check if all order_executors files are present
            assert os.path.isfile(
                os.path.join(
                    tempdir,
                    self.project_name,
                    'order_executors',
                    '__init__.py'
                )
            )
            assert os.path.isfile(
                os.path.join(
                    tempdir,
                    self.project_name,
                    'order_executors',
                    'order_executors.py'
                )
            )

    def test_project_name(self):

        with TemporaryDirectory() as tempdir:
            command = CreateStandardAlgorithmCommand()
            command.handle(name=random_string(10), directory=tempdir)

        with TemporaryDirectory() as tempdir:
            command = CreateStandardAlgorithmCommand()
            command.handle(
                name=random_string(10) + '_' + random_string(10),
                directory=tempdir
            )

        with pytest.raises(CommandError):
            with TemporaryDirectory() as tempdir:
                command = CreateStandardAlgorithmCommand()
                command.handle(
                    name=random_string(10) + ' ' + random_string(10),
                    directory=tempdir
                )
