import os
import subprocess
import re
import random
import string
import asyncio
import time

from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.web import WebSiteManagementClient

STORAGE_ACCOUNT_NAME_PREFIX = "iafstorageaccount"


def generate_unique_resource_name(base_name):
    """
    Function to generate a unique resource name by appending a random suffix.

    Args:
        base_name (str): The base name for the resource.

    Returns:
        str: The unique resource name.
    """
    unique_suffix = ''.join(
        random.choices(string.ascii_lowercase + string.digits, k=6)
    )
    return f"{base_name}{unique_suffix}".lower()


def ensure_azure_functools():
    """
    Function to ensure that the Azure Functions Core Tools are installed.
    If not, it will prompt the user to install it.
    """

    try:
        result = subprocess.run(
            ["func", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            raise FileNotFoundError("Azure Functions Core Tools not found.")
    except FileNotFoundError:
        print("Azure Functions Core Tools not found. Please install it.")
        print("You can install it using the following command:")
        print("npm install -g azure-functions-core-tools@4 --unsafe-perm true")
        exit(1)


async def read_env_file_and_set_function_env_variables(
    function_app_name,
    storage_connection_string,
    storage_container_name,
    resource_group_name
):
    """
    Function to read the .env file in the working directory
    and set the environment variables for the Function App.

    Returns:
        None
    """
    env_file_path = os.path.join(os.getcwd(), ".env")
    entries = {}
    if os.path.exists(env_file_path):
        with open(env_file_path, "r") as file:
            for line in file:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    entries[key] = value

        # Convert dictionary to CLI format
        settings = [f"{key}={value}" for key, value in entries.items()]

        # Construct the command
        command = [
            "az", "functionapp", "config", "appsettings", "set",
            "--name", function_app_name,
            "--resource-group", resource_group_name,
            "--settings"
        ] + settings  # Append all settings

        # Run the Azure CLI command asynchronously
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            print(
                "Environment variables successfully set for the function app."
            )
        else:
            print(
                "Error setting environment variables: " +
                f"{stderr.decode().strip()}"
            )

    else:
        print(f".env file not found at {env_file_path}")


async def publish_function_app(
    function_app_name,
    storage_connection_string,
    storage_container_name,
    resource_group_name
):
    """
    Function to publish the Function App using Azure Functions Core Tools.

    Args:
        function_app_name (str): Name of the Function App to publish.
        storage_connection_string (str): Azure Storage Connection String.
        storage_container_name (str): Azure Storage Container Name.
        resource_group_name (str): Resource Group Name.

    Returns:
        None
    """
    print(f"Publishing Function App {function_app_name}")

    # Wait for 60 seconds to ensure the Function App is ready
    time.sleep(60)

    try:
        # Step 1: Publish the Azure Function App
        process = await asyncio.create_subprocess_exec(
            "func", "azure", "functionapp", "publish", function_app_name
        )

        # Wait for the subprocess to finish
        _, stderr = await process.communicate()

        # Check the return code
        if process.returncode != 0:

            if stderr is not None:
                raise Exception(
                    f"Error publishing Function App: {stderr.decode().strip()}"
                )
            else:
                raise Exception("Error publishing Function App")

        print(f"Function App {function_app_name} published successfully.")

        # Step 2: Add app settings
        add_settings_process = await asyncio.create_subprocess_exec(
            "az", "functionapp", "config", "appsettings", "set",
            "--name", function_app_name,
            "--settings",
            f"AZURE_STORAGE_CONNECTION_STRING={storage_connection_string}",
            f"AZURE_STORAGE_CONTAINER_NAME={storage_container_name}",
            "--resource-group", resource_group_name
        )
        _, stderr1 = await add_settings_process.communicate()

        if add_settings_process.returncode != 0:

            if stderr1 is not None:
                raise Exception(
                    f"Error adding App settings: {stderr1.decode().strip()}"
                )
            else:
                raise Exception("Error adding App settings")

        print(
            "Added app settings to the Function App successfully"
        )

        # Step 3: Update the cors settings
        cors_process = await asyncio.create_subprocess_exec(
            "az", "functionapp", "cors", "add",
            "--name", function_app_name,
            "--allowed-origins", "*",
            "--resource-group", resource_group_name
        )

        _, stderr1 = await add_settings_process.communicate()

        if cors_process.returncode != 0:

            if stderr1 is not None:
                raise Exception(
                    f"Error adding cors settings: {stderr1.decode().strip()}"
                )
            else:
                raise Exception("Error adding cors settings")

        print("All app settings have been added successfully.")
        print("Function App creation completed successfully.")
    except Exception as e:
        print(f"Error publishing Function App: {e}")


async def create_function_app(
    resource_group_name,
    deployment_name,
    storage_account_name,
    region
):
    """
    Creates an Azure Function App in a Consumption Plan and deploys
      a Python Function.

    Args:
        resource_group_name (str): Resource group name.
        deployment_name (str): Name of the Function App to create.
        storage_account_name (str): Name of the associated Storage Account.
        region (str): Azure region (e.g., "eastus").

    Returns:
        dict: Details of the created or existing Function App.
    """
    # Check if the Function App already exists
    print(f"Checking if Function App '{deployment_name}' exists...")

    try:
        # Check for the Function App
        check_process = await asyncio.create_subprocess_exec(
            "az",
            "functionapp",
            "show",
            "--name",
            deployment_name,
            "--resource-group",
            resource_group_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await check_process.communicate()

        if check_process.returncode == 0:
            # The Function App exists, return details
            print(f"Function App '{deployment_name}' already exists.")
            return stdout.decode()

        # If the return code is non-zero, and the error indicates
        # the Function App doesn't exist, proceed to create it
        if "ResourceNotFound" in stderr.decode():
            print(
                f"Function App '{deployment_name}' does not exist." +
                " Proceeding to create it..."
            )
        else:
            # If the error is something else, raise it
            print(f"Error checking for Function App: {stderr.decode()}")
            raise Exception(stderr.decode())

        # Create the Function App
        print(f"Creating Function App '{deployment_name}'...")
        create_process = await asyncio.create_subprocess_exec(
            "az",
            "functionapp",
            "create",
            "--resource-group",
            resource_group_name,
            "--consumption-plan-location",
            region,
            "--runtime",
            "python",
            "--runtime-version",
            "3.10",
            "--functions-version",
            "4",
            "--name",
            deployment_name,
            "--os-type",
            "linux",
            "--storage-account",
            storage_account_name
        )

        # Wait for the subprocess to finish
        _, create_stderr = await create_process.communicate()

        # Check the return code for the create command
        if create_process.returncode != 0:
            print(
                "Error creating Function App: " +
                f"{create_stderr.decode().strip()}"
            )
            raise Exception(
                "Error creating Function App: " +
                f"{create_stderr.decode().strip()}"
            )

        print(f"Function App '{deployment_name}' created successfully.")
        return {"status": "created"}

    except Exception as e:
        print(f"Error creating Function App: {e}")
        raise e


def create_file_from_template(template_path, output_path):
    """
    Creates a new file by replacing placeholders in a template file.

    Args:
        template_path (str): The path to the template file.
        output_path (str): The path to the output file.
        replacements (dict): A dictionary of placeholder
            keys and their replacements.

    Returns:
        None
    """
    with open(template_path, "r") as file:
        template = file.read()

    with open(output_path, "w") as file:
        file.write(template)


def ensure_consumption_plan(
    resource_group_name,
    plan_name,
    region,
    subscription_id,
    credential
):
    """
    Ensures that an App Service Plan with the Consumption Plan exists.
    If not, creates it.

    Args:
        resource_group_name (str): The name of the resource group.
        plan_name (str): The name of the App Service Plan.
        region (str): The Azure region for the resources.
        subscription_id (str): The Azure subscription ID.

    Returns:
        object: The App Service Plan object.
    """
    web_client = WebSiteManagementClient(credential, subscription_id)

    try:
        print(
            f"Checking if App Service Plan '{plan_name}' exists" +
            f" in resource group '{resource_group_name}'..."
        )
        plan = web_client.app_service_plans.get(resource_group_name, plan_name)
        print(f"App Service Plan '{plan_name}' already exists.")
    except Exception:  # Plan does not exist
        print(
            f"App Service Plan '{plan_name}' not found. " +
            "Creating it as a Consumption Plan..."
        )
        plan = web_client.app_service_plans.begin_create_or_update(
            resource_group_name,
            plan_name,
            {
                "location": region,
                "sku": {"name": "Y1", "tier": "Dynamic"},
                "kind": "functionapp",  # Mark this as for Function Apps
                "properties": {}
            },
        ).result()
        print(f"App Service Plan '{plan_name}' created successfully.")
    return plan


def ensure_storage_account(
    storage_account_name,
    resource_group_name,
    region,
    subscription_id,
    credential,
):
    """
    Checks if a storage account exists. If it doesn't, creates it.

    If no storage account name is provided, a unique name will
    be generated. However, before we create a new
    storage account, we check if there a storage account exists
    with the prefix 'iafstorageaccount'. If it exists, we use
    that storage account.

    Args:
        storage_account_name (str): The name of the storage account.
        resource_group_name (str): The name of the resource group.
        region (str): The Azure region for the resources.
        subscription_id (str): The Azure subscription ID.
        credential: Azure credentials object.

    Returns:
        StorageAccount: The created storage account object.
    """
    # Create Storage Management Client
    storage_client = StorageManagementClient(credential, subscription_id)

    # Check if the storage account exists
    try:

        # Check if provided storage account name has prefix 'iafstorageaccount'
        if storage_account_name.startswith(STORAGE_ACCOUNT_NAME_PREFIX):
            # List all storage accounts in the resource group
            storage_accounts = storage_client\
                .storage_accounts.list_by_resource_group(
                    resource_group_name
                )

            for account in storage_accounts:
                if account.name.startswith(STORAGE_ACCOUNT_NAME_PREFIX):
                    storage_account_name = account.name
                    break

        storage_client.storage_accounts.get_properties(
            resource_group_name,
            storage_account_name,
        )
        print(f"Storage account '{storage_account_name}' already exists.")
        account_key = storage_client.storage_accounts.list_keys(
            resource_group_name,
            storage_account_name,
        ).keys[1].value
        connection_string = "DefaultEndpointsProtocol=https;" + \
            f"AccountName={storage_account_name};" + \
            f"AccountKey={account_key};EndpointSuffix=core.windows.net"
        return connection_string, storage_account_name
    except Exception:  # If the storage account does not exist
        print("Creating storage account ...")

        # Create storage account
        storage_async_operation = storage_client.storage_accounts.begin_create(
            resource_group_name,
            storage_account_name,
            {
                "location": region,
                "sku": {"name": "Standard_LRS"},
                "kind": "StorageV2",
            },
        )
        storage_async_operation.result()

        if storage_async_operation.status() == "Succeeded":
            print(
                f"Storage account '{storage_account_name}'" +
                "created successfully."
            )

        account_key = storage_client.storage_accounts\
            .list_keys(
                resource_group_name,
                storage_account_name,
            ).keys[1].value
        connection_string = f"DefaultEndpointsProtocol=https;"\
            f"AccountName={storage_account_name};" + \
            f"AccountKey={account_key};" + \
            "EndpointSuffix=core.windows.net"
        return connection_string, storage_account_name


def ensure_az_login(skip_check=False):
    """
    Ensures the user is logged into Azure using `az login`.
    If not logged in, it will prompt the user to log in.

    Raises:
        Exception: An error occurred during the login process.
    """

    if skip_check:
        return

    result = subprocess.run(["az", "login"], check=True)

    if result.returncode != 0:
        raise Exception("An error occurred during 'az login'.")


def get_default_subscription_id():
    """
    Fetches the default subscription ID using Azure CLI.

    Returns:
        str: The default subscription ID.
    """
    print("Fetching default subscription ID...")

    # Check if an default subscription ID is set in the environment
    if "AZURE_SUBSCRIPTION_ID" in os.environ:
        return os.environ["AZURE_SUBSCRIPTION_ID"]

    try:
        print(
            "If you want to use a different subscription, please provide the"
            " subscription ID with the '--subscription_id' option or"
            " by setting the 'AZURE_SUBSCRIPTION_ID' environment variable."
        )
        result = subprocess.run(
            ["az", "account", "show", "--query", "id", "-o", "tsv"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        subscription_id = result.stdout.strip()
        print(f"Default subscription ID: {subscription_id}")
        return subscription_id
    except subprocess.CalledProcessError:
        print(
            "Error fetching default subscription ID." +
            " Please log in with 'az login'."
        )
        raise


def ensure_resource_group(
    resource_group_name,
    region,
    subscription_id,
    create_if_not_exists
):
    """
    Checks if a resource group exists. If it doesn't,
     creates it if `create_if_not_exists` is True.

    Args:
        resource_group_name (str): The name of the resource group.
        region (str): The Azure region for the resources.
        subscription_id (str): The Azure subscription ID.
        create_if_not_exists (bool): Flag to create the
            resource group if it does not exist.

    Returns:
        None
    """
    credential = DefaultAzureCredential()
    resource_client = ResourceManagementClient(credential, subscription_id)

    print(f"Checking if resource group '{resource_group_name}' exists...")
    try:
        resource_client.resource_groups.get(resource_group_name)
        print(f"Resource group '{resource_group_name}' already exists.")
    except Exception:  # If the resource group does not exist

        try:
            if create_if_not_exists:
                print(
                    f"Resource group '{resource_group_name}' not" +
                    " found. Creating it..."
                )
                resource_client.resource_groups.create_or_update(
                    resource_group_name,
                    {"location": region},
                )
                print(
                    f"Resource group '{resource_group_name}'" +
                    " created successfully."
                )
            else:
                print(
                    f"Resource group '{resource_group_name}' does" +
                    " not exist, and 'create_if_not_exists' is False."
                )
                raise ValueError(
                    f"Resource group '{resource_group_name}' does not exist."
                )
        except Exception as e:
            raise Exception(f"Error creating resource group: {e}")


def create_storage_and_function(
    resource_group_name,
    storage_account_name,
    container_name,
    deployment_name,
    region,
    subscription_id=None,
    create_resource_group_if_not_exists=False,
    skip_login=False
):

    # Make sure that the deployment name only contains lowercase letters, and
    # uppercase letters
    regex = r"^[a-zA-Z0-9]+$"
    if not re.match(regex, deployment_name):
        raise ValueError(
            "--deployment_name can only contain " +
            "letters (uppercase and lowercase)."
        )
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

    create_file_from_template(
        template_host_file_path, os.path.join(cwd, "host.json")
    )

    create_file_from_template(
        template_settings_path, os.path.join(cwd, "local.settings.json")
    )

    # Fetch default subscription ID if not provided
    if not subscription_id:
        subscription_id = get_default_subscription_id()

    # Authenticate using DefaultAzureCredential
    # (requires environment variables or Azure CLI login)
    credential = DefaultAzureCredential()

    # Check if the resource group exists
    ensure_resource_group(
        resource_group_name,
        region,
        subscription_id,
        create_resource_group_if_not_exists
    )

    if storage_account_name is None:
        storage_account_name = \
            generate_unique_resource_name(STORAGE_ACCOUNT_NAME_PREFIX)

    # Ensure storage account exists
    storage_account_connection_string, storage_account_name = \
        ensure_storage_account(
            storage_account_name,
            resource_group_name,
            region,
            subscription_id,
            credential
        )

    # Create Function App
    asyncio.run(
        create_function_app(
            resource_group_name=resource_group_name,
            deployment_name=deployment_name,
            region=region,
            storage_account_name=storage_account_name
        )
    )

    # Publish Function App
    asyncio.run(
        publish_function_app(
            function_app_name=deployment_name,
            storage_connection_string=storage_account_connection_string,
            storage_container_name=container_name,
            resource_group_name=resource_group_name
        )
    )

    print(
        f"Function App '{deployment_name}' deployment" +
        "completed successfully."
    )


def command(
    resource_group,
    subscription_id,
    storage_account_name,
    container_name,
    deployment_name,
    region,
    create_resource_group_if_not_exists,
    skip_login
):
    """
    Command-line tool for creating an Azure storage account,
        blob container, and Function App.

    Args:
        resource_group (str): The name of the resource group.
        subscription_id (str): The Azure subscription ID.
        storage_account_name (str): The name of the storage account.
        container_name (str): The name of the blob container.
        function_app (str): The name of the Azure Function App.
        region (str): The Azure region for the resources.
        create_resource_group_if_not_exists (bool): Flag to create
            the resource group if it does not exist.

    Returns:
        None
    """

    print("logging in to Azure...")
    # Ensure the user is logged in
    ensure_az_login(skip_check=skip_login)

    print("Checking functools...")
    # Ensure azure functions core tools are installed
    ensure_azure_functools()

    create_storage_and_function(
        resource_group_name=resource_group,
        storage_account_name=storage_account_name,
        container_name=container_name,
        deployment_name=deployment_name,
        region=region,
        subscription_id=subscription_id,
        skip_login=skip_login,
        create_resource_group_if_not_exists=create_resource_group_if_not_exists
    )
