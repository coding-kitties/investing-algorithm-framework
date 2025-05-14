import os
from enum import Enum


class AppType(Enum):
    DEFAULT = "DEFAULT"
    DEFAULT_WEB = "DEFAULT_WEB"
    AZURE_FUNCTION = "AZURE_FUNCTION"

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


def command(path=None, app_type="default", replace=False):
    """
    Function to create an azure function app skeleton.

    Args:
        path (str): Path to directory to initialize the app in.
        app_type (str): Type of app to create. Options are: 'default',
            'default-web', 'azure-function'.
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
            print(f"Directory {path} does not exist.")
            return

    # Get the path of this script (command.py)
    current_script_path = os.path.abspath(__file__)

    if AppType.DEFAULT.equals(app_type):
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
    elif AppType.DEFAULT_WEB.equals(app_type):
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
    elif AppType.AZURE_FUNCTION.equals(app_type):
        # Construct the path to the template file
        template_app_file_path = os.path.join(
            os.path.dirname(current_script_path),
            "templates",
            "app_azure_function.py.template"
        )
        requirements_path = os.path.join(
            os.path.dirname(current_script_path),
            "templates",
            "requirements_azure_function.txt.template"
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

        # Create the framework app file as app_entry.py
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
    else:
        raise ValueError(
            f"Invalid app type: {app_type}. "
            "Valid options are: 'default', 'default_web', 'azure_function'."
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
    # Create the main directory
    create_directory(os.path.join(path, "strategies"))
    strategies_path = os.path.join(path, "strategies")
    create_file(os.path.join(strategies_path, "__init__.py"))
    create_file_from_template(
        strategy_template_path,
        os.path.join(strategies_path, "strategy.py")
    )
    create_file_from_template(
        data_providers_template_path,
        os.path.join(strategies_path, "data_providers.py"),
        replace=replace
    )
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
