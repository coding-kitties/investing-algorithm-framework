import os


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


def create_file(file_path):
    """
    Creates a new file.

    Args:
        file_path (str): The path to the file to create.

    Returns:
        None
    """

    if not os.path.exists(file_path):
        with open(file_path, "w") as file:
            file.write("")


def create_file_from_template(template_path, output_path):
    """
    Creates a new file by replacing placeholders in a template file.

    Args:
        template_path (str): The path to the template file.
        output_path (str): The path to the output file.
        replacements (dict): A dictionary of placeholder keys and
        their replacements.

    Returns:
        None
    """

    # Check if output path already exists
    if not os.path.exists(output_path):
        with open(template_path, "r") as file:
            template = file.read()

        with open(output_path, "w") as file:
            file.write(template)




def command(path = None, web = False):
    """
    Function to create an azure function app skeleton.

    Args:
        create_app_skeleton (bool): Flag to create an app skeleton.

    Returns:
        None
    """

    if path == None:
        path = os.getcwd()
    else:
        # check if directory exists
        if not os.path.exists(path) or not os.path.isdir(path):
            print(f"Directory {path} does not exist.")
            return

    # Get the path of this script (command.py)
    current_script_path = os.path.abspath(__file__)

    if web:
        # Construct the path to the template file
        template_app_file_path = os.path.join(
            os.path.dirname(current_script_path),
            "templates",
            "app-web.py.template"
        )
    else:
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
    strategy_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "strategy.py.template"
    )
    run_backtest_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "run_backtest.py.template"
    )
    market_data_providers_template_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "market_data_providers.py.template"
    )

    create_file(os.path.join(path, "__init__.py"))
    create_file_from_template(
        template_app_file_path,
        os.path.join(path, "app.py")
    )
    create_file_from_template(
        requirements_path,
        os.path.join(path, "requirements.txt")
    )
    create_file_from_template(
        run_backtest_template_path,
        os.path.join(path, "run_backtest.py")
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
        market_data_providers_template_path,
        os.path.join(path, "market_data_providers.py")
    )
    print(
        "App initialized successfully. "
    )
