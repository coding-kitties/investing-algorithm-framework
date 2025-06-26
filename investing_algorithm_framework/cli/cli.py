import click

from .deploy_to_aws_lambda import command as deploy_to_aws_lambda_command
from .deploy_to_azure_function import command as \
    deploy_to_azure_function_command
from .initialize_app import command as initialize_app_command

"""
CLI for Investing Algorithm Framework

This module provides a command-line interface (CLI) for the
Investing Algorithm Framework.
"""


@click.group()
def cli():
    """CLI for Investing Algorithm Framework"""
    pass


@click.command()
@click.option(
    '--type',
    default="default",
    help="Type of app to create. "
    "Options are: 'default', 'default_web', 'azure_function'."
)
@click.option(
    '--path', default=None, help="Path to directory to initialize the app in"
)
@click.option(
    '--replace',
    is_flag=True,
    default=False,
    help="If True, duplicate files will be replaced."
    "If False, files will not be replaced."
)
def init(type, path, replace):
    """
    Command-line tool for creating an app skeleton.

    Args:
        type (str): Type of app to create. Options are: 'default',
            'default-web', 'azure-function'.
        path (str): Path to directory to initialize the app in
        replace (bool): If True, existing files will be replaced.
            If False, existing files will not be replaced.

    Returns:
        None
    """
    initialize_app_command(path=path, app_type=type, replace=replace)


@click.command()
@click.option(
    '--resource_group',
    required=True,
    help='The name of the resource group.',
)
@click.option(
    '--subscription_id',
    required=False,
    help='The subscription ID. If not provided, the default will be used.'
)
@click.option(
    '--storage_account_name',
    required=False,
    help='The name of the storage account.',
)
@click.option(
    '--container_name',
    required=False,
    help='The name of the blob container.',
    default='iafcontainer'
)
@click.option(
    '--deployment_name',
    required=True,
    help='The name of the deployment. This will be" + \
        "used as the name of the Function App.'
)
@click.option(
    '--region',
    required=True,
    help='The Azure region for the resources.'
)
@click.option(
    '--create_resource_group_if_not_exists',
    is_flag=True,
    help='Flag to create the resource group if it does not exist.'
)
@click.option(
    '--skip_login',
    is_flag=True,
    help='Flag to create the resource group if it does not exist.',
    default=False
)
def deploy_azure_function(
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
    Command-line tool for deploying a trading bot to Azure Function.

    Args:
        path (str): Path to directory to initialize the app in
        resource_group (str): The name of the resource group.
        subscription_id (str): The subscription ID. If not provided,
            the default will be used.
        storage_account_name (str): The name of the storage account.
        container_name (str): The name of the blob container.
        deployment_name (str): The name of the deployment. This will be
            used as the name of the Function App.
        region (str): The Azure region for the resources.
        create_resource_group_if_not_exists (bool): Flag to create the
            resource group if it does not exist.
        skip_login (bool): Flag to skip the login process. This is
            useful for CI/CD pipelines where the login is handled
            separately.
        region (str): The Azure region for the resources.
        create_resource_group_if_not_exists (bool): Flag to create the
            resource group if it does not exist.
        skip_login (bool): Flag to skip the login process. This is
            useful for CI/CD pipelines where the login is handled
            separately.

    Returns:
        None
    """
    crg = create_resource_group_if_not_exists
    deploy_to_azure_function_command(
        resource_group=resource_group,
        subscription_id=subscription_id,
        storage_account_name=storage_account_name,
        container_name=container_name,
        deployment_name=deployment_name,
        region=region,
        create_resource_group_if_not_exists=crg,
        skip_login=skip_login
    )


@click.command()
@click.option(
    '--lambda_function_name',
    required=True,
    help='The name of the AWS Lambda function to deploy.'
)
@click.option(
    '--region',
    required=True,
    help='The AWS region where the Lambda function will be deployed.'
)
@click.option(
    '--lambda_handler',
    required=True,
    help='The Lambda handler function in the '
         'format "module_name.function_name".',
    default="aws_function.lambda_handler"
)
@click.option(
    '--project_dir',
    default=None,
    help='The path to the project directory containing '
         'the Lambda function code.'
)
def deploy_aws_lambda(
    lambda_function_name,
    region,
    lambda_handler,
    project_dir=None,
):
    """
    Command-line tool for deploying a trading bot to AWS lambda

    Args:
        lambda_function_name (str): The name of the AWS Lambda function
            to deploy.
        region (str): The AWS region where the Lambda function will
            be deployed.
        lambda_handler (str): The Lambda handler function in the format
            "module_name.function_name".
        project_dir (str): The path to the project directory containing the
            Lambda function code. If not provided, it defaults to
            the current directory.

    Returns:
        None
    """
    deploy_to_aws_lambda_command(
        lambda_function_name=lambda_function_name,
        region=region,
        lambda_handler=lambda_handler,
        project_dir=project_dir
    )


cli.add_command(init)
cli.add_command(deploy_azure_function)
