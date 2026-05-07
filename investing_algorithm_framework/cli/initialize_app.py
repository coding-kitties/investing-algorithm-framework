import json
import os
from enum import Enum


# Notebook stubs created in `notebooks/` by `init`. Each entry is
# (filename, first-markdown-cell-title) and mirrors the recommended
# research workflow documented in
# docusaurus/docs/Getting Started/application-setup.md.
RECOMMENDED_NOTEBOOKS = [
    ("01_data_exploration.ipynb",
     "# 01 — Data Exploration\n\nDownload OHLCV, inspect coverage, "
     "detect and fill gaps."),
    ("02_backtest_baseline.ipynb",
     "# 02 — Baseline Backtest\n\nSingle vector backtest of the strategy "
     "with default parameters and HTML report."),
    ("03_in_sample_param_grid_search.ipynb",
     "# 03 — In-Sample Parameter Grid Search\n\nGrid search across "
     "thousands of parameter combinations on the in-sample window."),
    ("04_out_of_sample_param_grid_search.ipynb",
     "# 04 — Out-of-Sample Parameter Grid Search\n\nRe-run top in-sample "
     "candidates on the held-out out-of-sample window."),
    ("05_overfitting_analysis.ipynb",
     "# 05 — Overfitting Analysis\n\nCompare in-sample vs out-of-sample "
     "performance, walk-forward / permutation checks."),
    ("06_event_backtests.ipynb",
     "# 06 — Event-Driven Backtests\n\nValidate the final picks with the "
     "event-driven engine (fees, slippage, fills)."),
]

# Empty cache/output directories created in the project root.
RECOMMENDED_DIRS = ["data", "backtest_results", "reports", "resources"]


class AppType(Enum):
    DEFAULT = "DEFAULT"
    DEFAULT_WEB = "DEFAULT_WEB"
    AZURE_FUNCTION = "AZURE_FUNCTION"
    AWS_LAMBDA = "AWS_LAMBDA"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for app_type in AppType:

                if value.upper() == app_type.value:
                    return app_type

        raise ValueError("Could not convert value to AppType")

    @staticmethod
    def from_value(value):

        if isinstance(value, AppType):
            for app_type in AppType:

                if value == app_type:
                    return app_type

        elif isinstance(value, str):
            return AppType.from_string(value)

        raise ValueError(f"Could not convert value {value} to AppType")

    def equals(self, other):
        return AppType.from_value(other) == self


def create_directory(directory_path):
    """
    Creates a new directory.

    Args:
        directory_path (str): The path to the directory to create.

    Returns:
        None
    """

    if not os.path.exists(directory_path):
        os.makedirs(directory_path)


def create_file(file_path, replace=False):
    """
    Creates a new file.

    Args:
        file_path (str): The path to the file to create.

    Returns:
        None
    """

    # Check if file already exists
    if os.path.exists(file_path):
        if replace:
            os.remove(file_path)

    if not os.path.exists(file_path):
        with open(file_path, "w") as file:
            file.write("")


def create_file_from_template(template_path, output_path, replace=False):
    """
    Creates a new file by replacing placeholders in a template file.

    Args:
        template_path (str): The path to the template file.
        output_path (str): The path to the output file.
        replacements (dict): A dictionary of placeholder keys and
        their replacements.
        replace (bool): If True, the template file will be replaced

    Returns:
        None
    """
    if replace:
        if os.path.exists(output_path):
            os.remove(output_path)

    # Check if output path already exists
    if not os.path.exists(output_path):
        with open(template_path, "r") as file:
            template = file.read()

        with open(output_path, "w") as file:
            file.write(template)


def _create_empty_notebook(file_path, title_markdown, replace=False):
    """
    Create a minimal Jupyter notebook (nbformat 4) with a single
    markdown title cell.
    """
    if os.path.exists(file_path):
        if replace:
            os.remove(file_path)
        else:
            return

    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": title_markdown,
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    with open(file_path, "w") as file:
        json.dump(notebook, file, indent=1)


def _scaffold_recommended_layout(path, replace=False):
    """
    Create the directories and notebook stubs that are part of the
    recommended project layout but not directly tied to a specific
    deployment target (default, web, AWS Lambda, Azure Function).

    Creates:
        notebooks/                  with 6 stub research notebooks
        data/                       cache for downloaded market data
        backtest_results/           saved backtest bundles
        reports/                    generated HTML/CSV reports
        resources/                  misc assets (databases, configs)
    """
    notebooks_path = os.path.join(path, "notebooks")
    create_directory(notebooks_path)

    for filename, title_markdown in RECOMMENDED_NOTEBOOKS:
        _create_empty_notebook(
            os.path.join(notebooks_path, filename),
            title_markdown,
            replace=replace,
        )

    for directory_name in RECOMMENDED_DIRS:
        directory_path = os.path.join(path, directory_name)
        create_directory(directory_path)
        # .gitkeep so the empty directory is committed
        create_file(os.path.join(directory_path, ".gitkeep"))


def command(path=None, app_type="default", replace=False):
    """
    Function to create an azure function app skeleton.

    Args:
        path (str): Path to directory to initialize the app in.
        app_type (str): Type of app to create. Options are: 'default',
            'default-web', 'azure-function', 'aws-lambda'.
        replace (bool): If True, existing files will be replaced.
            If False, existing files will not be replaced.
            Default is False.

    Returns:
        None
    """

    if path is None:
        path = os.getcwd()
    else:
        # check if directory exists
        if not os.path.exists(path) or not os.path.isdir(path):
            return

    if AppType.DEFAULT.equals(app_type):
        create_default_app(path=path, replace=replace)
    elif AppType.DEFAULT_WEB.equals(app_type):
        create_default_web_app(path=path, replace=replace)
    elif AppType.AZURE_FUNCTION.equals(app_type):
        create_azure_function_app(path=path, replace=replace)
    elif AppType.AWS_LAMBDA.equals(app_type):
        create_aws_lambda_app(path=path, replace=replace)
    else:
        raise ValueError(
            f"Unknown app type: {app_type}. "
            "Supported types are: 'default', 'default-web', "
            "'azure-function', 'aws-lambda'."
        )


def create_default_app(path=None, replace=False):
    """
    Function to create a default app skeleton.

    Args:
        path (str): Path to directory to initialize the app in.
        replace (bool): If True, existing files will be replaced.
            If False, existing files will not be replaced.
            Default is False.

    Returns:
        None
    """
    # Get the path of this script (command.py)
    current_script_path = os.path.abspath(__file__)

    # Construct the path to the template file
    template_app_file_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "app.py.template"
    )
    requirements_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "requirements.txt.template"
    )
    run_backtest_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "run_backtest.py.template"
    )
    env_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "env.example.template"
    )
    create_file_from_template(
        env_template_path,
        os.path.join(path, ".env.example"),
        replace=replace
    )
    strategy_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "strategy.py.template"
    )
    data_providers_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "data_providers.py.template"
    )
    create_file(os.path.join(path, "__init__.py"))
    create_file_from_template(
        template_app_file_path,
        os.path.join(path, "app.py"),
        replace=replace
    )
    create_file_from_template(
        requirements_path,
        os.path.join(path, "requirements.txt"),
        replace=replace
    )
    create_file_from_template(
        run_backtest_template_path,
        os.path.join(path, "run_backtest.py"),
        replace=replace
    )
    # Create the strategies package
    create_directory(os.path.join(path, "strategies"))
    strategies_path = os.path.join(path, "strategies")
    create_file(os.path.join(strategies_path, "__init__.py"))
    create_file_from_template(
        strategy_template_path,
        os.path.join(strategies_path, "my_strategy.py")
    )
    # data_providers.py lives at the project root so app.py, notebooks
    # and strategies can all import it as `from data_providers import ...`
    create_file_from_template(
        data_providers_template_path,
        os.path.join(path, "data_providers.py"),
        replace=replace
    )
    _scaffold_recommended_layout(path, replace=replace)
    gitignore_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        ".gitignore.template"
    )
    create_file_from_template(
        gitignore_template_path,
        os.path.join(path, ".gitignore"),
        replace=replace
    )
    readme_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "readme.md.template"
    )
    create_file_from_template(
        readme_template_path,
        os.path.join(path, "README.md"),
        replace=replace
    )


def create_default_web_app(path=None, replace=False):
    """
    Function to create a default web app skeleton.

    Args:
        path (str): Path to directory to initialize the app in.
        replace (bool): If True, existing files will be replaced.
            If False, existing files will not be replaced.
            Default is False.

    Returns:
        None
    """
    # Get the path of this script (command.py)
    current_script_path = os.path.abspath(__file__)

    # Construct the path to the template file
    template_app_file_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "app_web.py.template"
    )
    requirements_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "requirements.txt.template"
    )
    run_backtest_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "run_backtest.py.template"
    )
    env_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "env.example.template"
    )
    create_file_from_template(
        env_template_path,
        os.path.join(path, ".env.example"),
        replace=replace
    )
    strategy_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "strategy.py.template"
    )

    data_providers_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "data_providers.py.template"
    )
    create_file(os.path.join(path, "__init__.py"))
    create_file_from_template(
        template_app_file_path,
        os.path.join(path, "app.py"),
        replace=replace
    )
    create_file_from_template(
        requirements_path,
        os.path.join(path, "requirements.txt"),
        replace=replace
    )
    create_file_from_template(
        run_backtest_template_path,
        os.path.join(path, "run_backtest.py"),
        replace=replace
    )
    # Create the strategies package
    create_directory(os.path.join(path, "strategies"))
    strategies_path = os.path.join(path, "strategies")
    create_file(os.path.join(strategies_path, "__init__.py"))
    create_file_from_template(
        strategy_template_path,
        os.path.join(strategies_path, "my_strategy.py")
    )
    # data_providers.py lives at the project root so app.py, notebooks
    # and strategies can all import it as `from data_providers import ...`
    create_file_from_template(
        data_providers_template_path,
        os.path.join(path, "data_providers.py"),
        replace=replace
    )
    _scaffold_recommended_layout(path, replace=replace)
    gitignore_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        ".gitignore.template"
    )
    create_file_from_template(
        gitignore_template_path,
        os.path.join(path, ".gitignore"),
        replace=replace
    )
    readme_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "readme.md.template"
    )
    create_file_from_template(
        readme_template_path,
        os.path.join(path, "README.md"),
        replace=replace
    )


def create_aws_lambda_app(path=None, replace=False):
    """
    Function to create an AWS Lambda app skeleton.

    Args:
        path (str): Path to directory to initialize the app in.
        replace (bool): If True, existing files will be replaced.
            If False, existing files will not be replaced.
            Default is False.

    Returns:
        None
    """
    # Get the path of this script (command.py)
    current_script_path = os.path.abspath(__file__)
    requirements_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "requirements.txt.template"
    )
    aws_lambda_handler_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "app_aws_lambda_function.py.template"
    )
    aws_dockerfile_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "aws_lambda_dockerfile.template"
    )
    aws_dockerignore_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "aws_lambda_dockerignore.template"
    )
    run_backtest_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "run_backtest.py.template"
    )
    env_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "env.example.template"
    )
    create_file_from_template(
        env_template_path,
        os.path.join(path, ".env"),
        replace=replace
    )
    strategy_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "strategy.py.template"
    )
    data_providers_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "data_providers.py.template"
    )
    create_file(os.path.join(path, "__init__.py"))
    create_file_from_template(
        requirements_path,
        os.path.join(path, "requirements.txt"),
        replace=replace
    )
    create_file_from_template(
        run_backtest_template_path,
        os.path.join(path, "run_backtest.py"),
        replace=replace
    )
    # Create the strategies package
    create_directory(os.path.join(path, "strategies"))
    strategies_path = os.path.join(path, "strategies")
    create_file(os.path.join(strategies_path, "__init__.py"))
    create_file_from_template(
        strategy_template_path,
        os.path.join(strategies_path, "my_strategy.py")
    )
    # data_providers.py lives at the project root so app.py, notebooks
    # and strategies can all import it as `from data_providers import ...`
    create_file_from_template(
        data_providers_template_path,
        os.path.join(path, "data_providers.py"),
        replace=replace
    )
    _scaffold_recommended_layout(path, replace=replace)
    gitignore_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        ".gitignore.template"
    )
    create_file_from_template(
        gitignore_template_path,
        os.path.join(path, ".gitignore"),
        replace=replace
    )
    readme_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "readme.md.template"
    )
    create_file_from_template(
        readme_template_path,
        os.path.join(path, "README.md"),
        replace=replace
    )
    create_file_from_template(
        aws_lambda_handler_template_path,
        os.path.join(path, "aws_function.py"),
        replace=replace
    )
    create_file_from_template(
        aws_dockerfile_template_path,
        os.path.join(path, "Dockerfile"),
        replace=replace
    )
    create_file_from_template(
        aws_dockerignore_template_path,
        os.path.join(path, ".dockerignore"),
        replace=replace
    )


def create_azure_function_app(path=None, replace=False):
    """
    Function to create an Azure Function app skeleton.

    Args:
        path (str): Path to directory to initialize the app in.
        replace (bool): If True, existing files will be replaced.
            If False, existing files will not be replaced.
            Default is False.

    Returns:
        None
    """
    # Get the path of this script (command.py)
    current_script_path = os.path.abspath(__file__)

    # Construct the path to the template file
    template_app_file_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "app_azure_function.py.template"
    )
    requirements_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "azure_function_requirements.txt.template"
    )
    azure_function_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "azure_function_function_app.py.template"
    )
    run_backtest_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "run_backtest.py.template"
    )
    # The Azure Functions Python v2 programming model requires the
    # entry point to be named exactly `function_app.py` at the project
    # root. Anything else and the host won't discover any triggers.
    create_file_from_template(
        azure_function_template_path,
        os.path.join(path, "function_app.py"),
        replace=replace
    )
    # Create the host.json file
    host_json_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "azure_function_host.json.template"
    )
    create_file_from_template(
        host_json_template_path,
        os.path.join(path, "host.json"),
        replace=replace
    )
    # Create the local.settings.json file
    local_settings_json_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "azure_function_local.settings.json.template"
    )
    create_file_from_template(
        local_settings_json_template_path,
        os.path.join(path, "local.settings.json"),
        replace=replace
    )
    env_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "env_azure_function.example.template"
    )
    create_file_from_template(
        env_template_path,
        os.path.join(path, ".env.example"),
        replace=replace
    )
    strategy_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "strategy.py.template"
    )
    data_providers_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "data_providers.py.template"
    )
    create_file(os.path.join(path, "__init__.py"))
    create_file_from_template(
        template_app_file_path,
        os.path.join(path, "app.py"),
        replace=replace
    )
    create_file_from_template(
        requirements_path,
        os.path.join(path, "requirements.txt"),
        replace=replace
    )
    create_file_from_template(
        run_backtest_template_path,
        os.path.join(path, "run_backtest.py"),
        replace=replace
    )
    # Create the strategies package
    create_directory(os.path.join(path, "strategies"))
    strategies_path = os.path.join(path, "strategies")
    create_file(os.path.join(strategies_path, "__init__.py"))
    create_file_from_template(
        strategy_template_path,
        os.path.join(strategies_path, "my_strategy.py")
    )
    # data_providers.py lives at the project root so app.py, notebooks
    # and strategies can all import it as `from data_providers import ...`
    create_file_from_template(
        data_providers_template_path,
        os.path.join(path, "data_providers.py"),
        replace=replace
    )
    _scaffold_recommended_layout(path, replace=replace)
    gitignore_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        ".gitignore.template"
    )
    create_file_from_template(
        gitignore_template_path,
        os.path.join(path, ".gitignore"),
        replace=replace
    )
    readme_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "readme.md.template"
    )
    create_file_from_template(
        readme_template_path,
        os.path.join(path, "README.md"),
        replace=replace
    )
