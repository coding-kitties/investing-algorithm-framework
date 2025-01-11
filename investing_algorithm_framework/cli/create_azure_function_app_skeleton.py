import os
import click


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


def create_azure_function_skeleton(
    add_app_template, add_requirements_template
):
    """
    Function to create an azure function app skeleton.

    Args:
        create_app_skeleton (bool): Flag to create an app skeleton.

    Returns:
        None
    """

    # Get current working directory
    cwd = os.getcwd()

    # Get the path of this script (command.py)
    current_script_path = os.path.abspath(__file__)

    # Construct the path to the template file
    template_host_file_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "azure_function_host.json.template"
    )
    template_settings_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "azure_function_local.settings.json.template"
    )
    function_app_path = os.path.join(
        os.path.dirname(current_script_path),
        "templates",
        "azure_function_function_app.py.template"
    )

    if add_app_template:
        function_app_path = os.path.join(
            os.path.dirname(current_script_path),
            "templates",
            "azure_function_framework_app.py.template"
        )
        create_file_from_template(
            function_app_path,
            os.path.join(cwd, "app_entry.py")
        )

    if add_requirements_template:
        requirements_path = os.path.join(
            os.path.dirname(current_script_path),
            "templates",
            "azure_function_requirements.txt.template"
        )
        create_file_from_template(
            function_app_path,
            os.path.join(cwd, "requirements.txt")
        )

    create_file(os.path.join(cwd, "__init__.py"))
    create_file_from_template(
        template_host_file_path,
        os.path.join(cwd, "host.json")
    )
    create_file_from_template(
        template_settings_path,
        os.path.join(cwd, "local.settings.json")
    )
    create_file_from_template(
        function_app_path,
        os.path.join(cwd, "function_app.py")
    )
    create_file_from_template(
        requirements_path,
        os.path.join(cwd, "requirements.txt")
    )
    print(
        "Function App trading bot skeleton creation completed"
    )


@click.command()
@click.option(
    '--add-app-template',
    is_flag=True,
    help='Flag to create an framework app skeleton',
    default=False
)
@click.option(
    '--add-requirements-template',
    is_flag=True,
    help='Flag to create an framework app skeleton',
    default=True
)
def cli(add_app_template, add_requirements_template):
    """
    Command-line tool for creating an azure function enabled app skeleton.

    Args:
        add_app_template (bool): Flag to create an app skeleton.
        add_requirements_template (bool): Flag to create a
        requirements template.

    Returns:
        None
    """
    create_azure_function_skeleton(add_app_template, add_requirements_template)
