"""
Tests for the CLI initialize command.

Streamlined from the original file which had 4 methods with ~80%
identical assertions. Now uses a shared helper for the common
file-existence and content checks, with per-app-type methods
that verify the differences (app file, requirements, env, etc.).
"""
import os
import shutil
from unittest import TestCase

from investing_algorithm_framework.cli.initialize_app import command


class TestAppInitialize(TestCase):

    def setUp(self) -> None:
        self.resource_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "resources"
        )
        self.template_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "investing_algorithm_framework", "cli", "templates"
        )
        self.output_dir = os.path.join(self.resource_dir, "output_cli")
        os.makedirs(self.output_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _template_path(self, filename):
        return os.path.join(self.template_dir, filename)

    def _output_path(self, *parts):
        return os.path.join(self.output_dir, *parts)

    def _assert_file_matches_template(self, output_file, template_name):
        """Assert that an output file exists and matches a template."""
        self.assertTrue(
            os.path.exists(output_file),
            f"Expected file not found: {output_file}"
        )
        with open(output_file) as f1, \
                open(self._template_path(template_name)) as f2:
            self.assertEqual(f1.read(), f2.read())

    def _assert_common_files(self):
        """Assert that the files common to ALL app types are present
        and match their templates."""
        strategy_dir = self._output_path("strategies")

        # Strategy directory exists
        self.assertTrue(os.path.isdir(strategy_dir))

        # strategy.py
        self._assert_file_matches_template(
            os.path.join(strategy_dir, "strategy.py"),
            "strategy.py.template"
        )

        # data_providers.py
        self._assert_file_matches_template(
            os.path.join(strategy_dir, "data_providers.py"),
            "data_providers.py.template"
        )

        # __init__.py in strategy dir
        self.assertTrue(
            os.path.exists(os.path.join(strategy_dir, "__init__.py"))
        )

        # __init__.py in root output
        self.assertTrue(
            os.path.exists(self._output_path("__init__.py"))
        )

        # run_backtest.py
        self._assert_file_matches_template(
            self._output_path("run_backtest.py"),
            "run_backtest.py.template"
        )

        # README.md
        self._assert_file_matches_template(
            self._output_path("README.md"),
            "readme.md.template"
        )

    # ------------------------------------------------------------------
    # App type: default
    # ------------------------------------------------------------------

    def test_init_command_default(self):
        command(path=self.output_dir, app_type="default")
        self._assert_common_files()

        # app.py
        self._assert_file_matches_template(
            self._output_path("app.py"), "app.py.template"
        )

        # requirements.txt
        self._assert_file_matches_template(
            self._output_path("requirements.txt"),
            "requirements.txt.template"
        )

        # .env.example
        self._assert_file_matches_template(
            self._output_path(".env.example"),
            "env.example.template"
        )

    # ------------------------------------------------------------------
    # App type: default_web
    # ------------------------------------------------------------------

    def test_init_command_web(self):
        command(path=self.output_dir, app_type="default_web")
        self._assert_common_files()

        # app.py (web variant)
        self._assert_file_matches_template(
            self._output_path("app.py"), "app_web.py.template"
        )

        # requirements.txt
        self._assert_file_matches_template(
            self._output_path("requirements.txt"),
            "requirements.txt.template"
        )

        # .env.example
        self._assert_file_matches_template(
            self._output_path(".env.example"),
            "env.example.template"
        )

    # ------------------------------------------------------------------
    # App type: azure_function
    # ------------------------------------------------------------------

    def test_init_command_azure_function(self):
        command(path=self.output_dir, app_type="azure_function")
        self._assert_common_files()

        # app.py (azure variant)
        self._assert_file_matches_template(
            self._output_path("app.py"),
            "app_azure_function.py.template"
        )

        # requirements.txt (azure variant)
        self._assert_file_matches_template(
            self._output_path("requirements.txt"),
            "azure_function_requirements.txt.template"
        )

        # .env.example (azure variant)
        self._assert_file_matches_template(
            self._output_path(".env.example"),
            "env_azure_function.example.template"
        )

    # ------------------------------------------------------------------
    # App type: aws_lambda
    # ------------------------------------------------------------------

    def test_init_command_aws_lambda(self):
        command(path=self.output_dir, app_type="aws_lambda")
        self._assert_common_files()

        # aws_function.py (not app.py)
        self._assert_file_matches_template(
            self._output_path("aws_function.py"),
            "app_aws_lambda_function.py.template"
        )

        # requirements.txt
        self._assert_file_matches_template(
            self._output_path("requirements.txt"),
            "requirements.txt.template"
        )

        # .env
        self._assert_file_matches_template(
            self._output_path(".env"),
            "env.example.template"
        )

        # Dockerfile
        self._assert_file_matches_template(
            self._output_path("Dockerfile"),
            "aws_lambda_dockerfile.template"
        )

        # .dockerignore
        self._assert_file_matches_template(
            self._output_path(".dockerignore"),
            "aws_lambda_dockerignore.template"
        )

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_all_app_types_produce_strategy_dir(self):
        """Every supported app type should produce a strategies/ dir."""
        for app_type in ("default", "default_web",
                         "azure_function", "aws_lambda"):
            with self.subTest(app_type=app_type):
                # Fresh output dir per sub-test
                sub_dir = self._output_path(f"sub_{app_type}")
                os.makedirs(sub_dir, exist_ok=True)
                command(path=sub_dir, app_type=app_type)
                self.assertTrue(
                    os.path.isdir(os.path.join(sub_dir, "strategies"))
                )
                shutil.rmtree(sub_dir)

    def test_init_command_idempotent(self):
        """Running the command twice should not fail."""
        command(path=self.output_dir, app_type="default")
        command(path=self.output_dir, app_type="default")
        self.assertTrue(
            os.path.exists(self._output_path("app.py"))
        )

