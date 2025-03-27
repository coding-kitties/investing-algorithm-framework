import os
from unittest import TestCase

from investing_algorithm_framework.cli.initialize_app import command


class TestAppInitialize(TestCase):

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.realpath(__file__),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )
        self.template_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.join(
                            os.path.realpath(__file__),
                            os.pardir
                        ),
                        os.pardir
                    ),
                    os.pardir
                ),
                "investing_algorithm_framework/cli/templates"
            )
        )

        self.output_dir = os.path.join(
            self.resource_dir,
            "output_cli"
        )

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def tearDown(self):
        self.remove_directory(self.output_dir)

    def test_init_command_default(self):
        command(
            path=self.output_dir, app_type="default"
        )

        # Check if app.py file exists
        app_file_path = os.path.join(self.output_dir, "app.py")
        self.assertTrue(os.path.exists(app_file_path))

        # Check if the app.py is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                app_file_path,
                os.path.join(self.template_dir, "app.py.template")
            )
        )

        # Check if requirements.txt file exists
        requirements_file_path = os.path.join(
            self.output_dir, "requirements.txt"
        )
        self.assertTrue(os.path.exists(requirements_file_path))

        # Check if the requirements.txt is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                requirements_file_path,
                os.path.join(self.template_dir, "requirements.txt.template")
            )
        )

        # Check if strategy dir exists
        strategy_dir_path = os.path.join(self.output_dir, "strategies")
        self.assertTrue(os.path.exists(strategy_dir_path))
        self.assertTrue(os.path.isdir(strategy_dir_path))

        # Check if strategy.py file exists
        strategy_file_path = os.path.join(
            strategy_dir_path, "strategy.py"
        )
        self.assertTrue(os.path.exists(strategy_file_path))
        # Check if the strategy.py is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                strategy_file_path,
                os.path.join(self.template_dir, "strategy.py.template")
            )
        )

        # Check if market_data_providers.py file exists
        market_data_providers_file_path = os.path.join(
            strategy_dir_path, "data_providers.py"
        )
        self.assertTrue(os.path.exists(market_data_providers_file_path))

        # Check if the market_data_providers.py is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                market_data_providers_file_path,
                os.path.join(self.template_dir, "data_providers.py.template")
            )
        )

        # Check if __init__.py file exists
        init_file_path = os.path.join(strategy_dir_path, "__init__.py")
        self.assertTrue(os.path.exists(init_file_path))

        # Check if __init__.py is in the root directory
        root_init_file_path = os.path.join(self.output_dir, "__init__.py")
        self.assertTrue(os.path.exists(root_init_file_path))

        # Check if run_backtest.py file exists
        run_backtest_file_path = os.path.join(self.output_dir, "run_backtest.py")
        self.assertTrue(os.path.exists(run_backtest_file_path))

        # Check if the run_backtest.py is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                run_backtest_file_path,
                os.path.join(self.template_dir, "run_backtest.py.template")
            )
        )

        # Check if readme.md file exists
        readme_file_path = os.path.join(self.output_dir, "README.md")

        self.assertTrue(os.path.exists(readme_file_path))

        # Check if the readme.md is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                readme_file_path,
                os.path.join(self.template_dir, "readme.md.template")
            )
        )

        # Check if there is a .env.example file
        env_example_file_path = os.path.join(self.output_dir, ".env.example")
        self.assertTrue(os.path.exists(env_example_file_path))
        # Check if the .env.example is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                env_example_file_path,
                os.path.join(self.template_dir, "env.example.template")
            )
        )

    def test_initialize_command_web(self):
        command(
            path=self.output_dir, app_type="default_web"
        )

        # Check if app.py file exists
        app_file_path = os.path.join(self.output_dir, "app.py")
        self.assertTrue(os.path.exists(app_file_path))

        # Check if the app.py is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                app_file_path,
                os.path.join(self.template_dir, "app_web.py.template")
            )
        )

        # Check if requirements.txt file exists
        requirements_file_path = os.path.join(
            self.output_dir, "requirements.txt"
        )
        self.assertTrue(os.path.exists(requirements_file_path))

        # Check if the requirements.txt is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                requirements_file_path,
                os.path.join(self.template_dir, "requirements.txt.template")
            )
        )

        # Check if strategy dir exists
        strategy_dir_path = os.path.join(self.output_dir, "strategies")
        self.assertTrue(os.path.exists(strategy_dir_path))
        self.assertTrue(os.path.isdir(strategy_dir_path))

        # Check if strategy.py file exists
        strategy_file_path = os.path.join(
            strategy_dir_path, "strategy.py"
        )
        self.assertTrue(os.path.exists(strategy_file_path))
        # Check if the strategy.py is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                strategy_file_path,
                os.path.join(self.template_dir, "strategy.py.template")
            )
        )

        # Check if market_data_providers.py file exists
        market_data_providers_file_path = os.path.join(
            strategy_dir_path, "data_providers.py"
        )
        self.assertTrue(os.path.exists(market_data_providers_file_path))

        # Check if the market_data_providers.py is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                market_data_providers_file_path,
                os.path.join(self.template_dir, "data_providers.py.template")
            )
        )

        # Check if __init__.py file exists
        init_file_path = os.path.join(strategy_dir_path, "__init__.py")
        self.assertTrue(os.path.exists(init_file_path))

        # Check if __init__.py is in the root directory
        root_init_file_path = os.path.join(self.output_dir, "__init__.py")
        self.assertTrue(os.path.exists(root_init_file_path))

        # Check if run_backtest.py file exists
        run_backtest_file_path = os.path.join(self.output_dir, "run_backtest.py")
        self.assertTrue(os.path.exists(run_backtest_file_path))

        # Check if the run_backtest.py is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                run_backtest_file_path,
                os.path.join(self.template_dir, "run_backtest.py.template")
            )
        )

        # Check if readme.md file exists
        readme_file_path = os.path.join(self.output_dir, "README.md")

        self.assertTrue(os.path.exists(readme_file_path))

        # Check if the readme.md is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                readme_file_path,
                os.path.join(self.template_dir, "readme.md.template")
            )
        )

        # Check if there is a .env.example file
        env_example_file_path = os.path.join(self.output_dir, ".env.example")
        self.assertTrue(os.path.exists(env_example_file_path))
        # Check if the .env.example is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                env_example_file_path,
                os.path.join(self.template_dir, "env.example.template")
            )
        )

    def test_initialize_command_azure_function(self):
        command(
            path=self.output_dir, app_type="azure_function"
        )

        # Check if app.py file exists
        app_file_path = os.path.join(self.output_dir, "app.py")
        self.assertTrue(os.path.exists(app_file_path))

        # Check if the app.py is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                app_file_path,
                os.path.join(self.template_dir, "app_azure_function.py.template")
            )
        )

        # Check if requirements.txt file exists
        requirements_file_path = os.path.join(
            self.output_dir, "requirements.txt"
        )
        self.assertTrue(os.path.exists(requirements_file_path))

        # Check if the requirements.txt is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                requirements_file_path,
                os.path.join(self.template_dir, "requirements_azure_function.txt.template")
            )
        )

        # Check if strategy dir exists
        strategy_dir_path = os.path.join(self.output_dir, "strategies")
        self.assertTrue(os.path.exists(strategy_dir_path))
        self.assertTrue(os.path.isdir(strategy_dir_path))

        # Check if strategy.py file exists
        strategy_file_path = os.path.join(
            strategy_dir_path, "strategy.py"
        )
        self.assertTrue(os.path.exists(strategy_file_path))
        # Check if the strategy.py is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                strategy_file_path,
                os.path.join(self.template_dir, "strategy.py.template")
            )
        )

        # Check if market_data_providers.py file exists
        market_data_providers_file_path = os.path.join(
            strategy_dir_path, "data_providers.py"
        )
        self.assertTrue(os.path.exists(market_data_providers_file_path))

        # Check if the market_data_providers.py is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                market_data_providers_file_path,
                os.path.join(self.template_dir, "data_providers.py.template")
            )
        )

        # Check if __init__.py file exists
        init_file_path = os.path.join(strategy_dir_path, "__init__.py")
        self.assertTrue(os.path.exists(init_file_path))

        # Check if __init__.py is in the root directory
        root_init_file_path = os.path.join(self.output_dir, "__init__.py")
        self.assertTrue(os.path.exists(root_init_file_path))

        # Check if run_backtest.py file exists
        run_backtest_file_path = os.path.join(self.output_dir, "run_backtest.py")
        self.assertTrue(os.path.exists(run_backtest_file_path))

        # Check if the run_backtest.py is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                run_backtest_file_path,
                os.path.join(self.template_dir, "run_backtest.py.template")
            )
        )

        # Check if readme.md file exists
        readme_file_path = os.path.join(self.output_dir, "README.md")

        self.assertTrue(os.path.exists(readme_file_path))

        # Check if the readme.md is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                readme_file_path,
                os.path.join(self.template_dir, "readme.md.template")
            )
        )

        # Check if there is a .env.example file
        env_example_file_path = os.path.join(self.output_dir, ".env.example")
        self.assertTrue(os.path.exists(env_example_file_path))
        # Check if the .env.example is the same as the template
        self.assertTrue(
            self.is_same_file_content(
                env_example_file_path,
                os.path.join(
                    self.template_dir, "env_azure_function.example.template"
                )
            )
        )

    def is_same_file_content(self, file1, file2):
        with open(file1, 'r') as f1, open(file2, 'r') as f2:
            content1 = f1.read()
            content2 = f2.read()
            return content1 == content2

    def remove_directory(self, path):
        if os.path.exists(path):
            for root, dirs, files in os.walk(path, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
