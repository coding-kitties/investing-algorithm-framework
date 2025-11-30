import json
import os
import re
import subprocess
import time
import zipfile

import boto3
import click

from investing_algorithm_framework.domain import AWS_S3_STATE_BUCKET_NAME


def sanitize_bucket_name(name: str) -> str:
    """
    Sanitize the bucket name to conform to AWS S3 bucket naming rules.
    AWS S3 bucket names must be globally unique, lowercase,
    and can only contain lowercase letters, numbers, and hyphens.
    They must start and end with a lowercase letter or number.

    An exception is raised if the name is invalid.

    Args:
        name: str, the name to sanitize.
    Returns:
        str: The sanitized bucket name.
    """
    # Lowercase, replace invalid chars with hyphen, and strip multiple hyphens
    name = name.lower()
    name = re.sub(r'[^a-z0-9-]', '-', name)
    name = re.sub(r'-+', '-', name).strip('-')

    # Check if the name exceeds the length limit
    if len(name) < 3 or len(name) > 63:
        raise ValueError(
            "Bucket name must be between 3 and 63 characters long."
        )

    return name  # Enforce length limit


def zip_code(source_dir, zip_file, ignore_dirs=None):
    """
    Recursively zips the contents of source_dir into zip_file,
    preserving directory structure — suitable for AWS Lambda deployment.

    Args:
        source_dir: str, the directory containing the Lambda function code.
        zip_file: str, the path where the zip file will be created.
        ignore_dirs: list, directories to ignore when zipping the code.

    Returns:
        None
    """
    click.echo(f"Zipping code from {source_dir} to {zip_file}")

    # Function should recursively zip all files and directories
    with zipfile.ZipFile(zip_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(source_dir):

            # Skip ignored directories
            if ignore_dirs is not None:
                relative_root = os.path.relpath(root, source_dir)
                if any(
                    relative_root.startswith(ignore) for ignore in ignore_dirs
                ):
                    click.echo(f"Ignoring directory: {relative_root}")
                    continue

            for file in files:
                click.echo(f"Adding {file} to zip")
                file_path = os.path.join(root, file)
                # Preserve the directory structure in the zip file
                arcname = os.path.relpath(file_path, source_dir)
                zf.write(file_path, arcname)


def create_iam_role(role_name):
    """
    Function to create an IAM role for AWS Lambda execution and access
    to the S3 bucket for state handling.
    This role allows Lambda functions to assume the
    role and execute with basic permissions and access to CloudWatch logs.
    Next to that the role will be able to access the S3 bucket
    for state handling.

    Args:
        role_name: str, the name of the IAM role to create.

    Returns:
        str: The ARN of the created or existing IAM role.
    """
    iam = boto3.client("iam")

    assume_policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }

    try:
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_policy)
        )
        click.echo(f"Created IAM Role: {role_name}")
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn=("arn:aws:iam::aws:policy/"
                       "service-role/AWSLambdaBasicExecutionRole")
        )
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess"
        )
        time.sleep(10)  # IAM roles may take a few seconds to propagate
        return role["Role"]["Arn"]
    except iam.exceptions.EntityAlreadyExistsException:
        click.echo(f"IAM Role {role_name} already exists.")
        return iam.get_role(RoleName=role_name)['Role']['Arn']


def deploy_lambda(
    function_name,
    region,
    image_uri,
    role_arn,
    memory_size,
    runtime="python3.10",
    env_vars=None,
):
    """
    Function to deploy a trading bot created with the framework to AWS Lambda.

    Args:
        function_name: str, the name of the Lambda function to
            create or update.
        region: str, the AWS region where the Lambda
            function will be deployed.
        image_uri: str, the URI of the Docker image in ECR.
        role_arn:  str, the ARN of the IAM role that Lambda will assume.
        runtime: str, the runtime environment for the
            Lambda function (default is "python3.10").
        env_vars: dict, optional environment variables
            to set for the Lambda function.
        memory_size: int, the amount of memory allocated
            to the Lambda function.

    Returns:
        None
    """
    lambda_client = boto3.client('lambda', region_name=region)

    try:
        lambda_client.get_function(FunctionName=function_name)
        click.echo(f"Function {function_name} already exists. Updating...")

        lambda_client.update_function_code(
            FunctionName=function_name,
            ImageUri=image_uri
        )
        wait_for_lambda_update(lambda_client, function_name, timeout=120)
        lambda_client.update_function_configuration(
            FunctionName=function_name,
            Environment={'Variables': env_vars or {}}
        )
    except lambda_client.exceptions.ResourceNotFoundException:
        click.echo(f"Creating new function: {function_name}")

        try:
            click.echo(
                "Creating new container-based "
                f"Lambda function: {function_name}"
            )
            lambda_client.create_function(
                FunctionName=function_name,
                Role=role_arn,
                PackageType="Image",
                Code={"ImageUri": image_uri},
                Timeout=900,
                MemorySize=memory_size,
                Environment={"Variables": env_vars or {}}
            )
        except Exception as e:
            raise click.ClickException(
                f"Failed to create Lambda function: {e}"
            )

    click.echo(f"Lambda function '{function_name}' deployed successfully.")


def s3_bucket_exists(bucket_name, region):
    """
    Function to check if an S3 bucket exists.

    Args:
        bucket_name: str, the name of the S3 bucket to check.
        region: str, the AWS region where the bucket is located.

    Returns:
        bool: True if the bucket exists, False otherwise.
    """
    s3 = boto3.client('s3', region_name=region)
    try:
        s3.head_bucket(Bucket=bucket_name)
        return True
    except s3.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            return False
        raise


def create_ecr_repository(repository_name, region):
    """
    Function to create an ECR repository for storing Docker images.
    It checks if the repository already exists and creates it if not.

    Args:
        repository_name: str, the name of the ECR repository to create.
        region: str, the AWS region where the repository will be created.

    Returns:
        None
    """

    ecr = boto3.client('ecr', region_name=region)
    try:
        response = ecr.create_repository(repositoryName=repository_name)
        click.echo(
            "Created ECR repository: "
            f"{response['repository']['repositoryUri']}"
        )
    except ecr.exceptions.RepositoryAlreadyExistsException:
        click.echo(f"ECR repository {repository_name} already exists.")


def build_and_push_docker_image(
    repository_name, region, dockerfile_path='Dockerfile', tag='latest'
):
    """
    Function to build a Docker image and push it to an ECR repository.

    Args:
        repository_name: str, the name of the ECR repository.
        region: str, the AWS region where the repository is located.
        dockerfile_path: str, path to the Dockerfile (default is 'Dockerfile').
        tag: str, the tag for the Docker image (default is 'latest').

    Returns:
        None
    """

    # Retrieve the ECR repository URI
    ecr = boto3.client('ecr', region_name=region)
    try:
        response = ecr.describe_repositories(repositoryNames=[repository_name])
        repository_uri = response['repositories'][0]['repositoryUri']
    except ecr.exceptions.RepositoryNotFoundException:
        raise click.ClickException(
            f"ECR repository {repository_name} does "
            f"not exist in region {region}."
        )

    # Authenticate Docker to the ECR registry
    auth = ecr.get_authorization_token()
    proxy = auth['authorizationData'][0]['proxyEndpoint']

    click.echo(f"Authenticating Docker to ECR repository {repository_name}...")
    subprocess.run(
        f"aws ecr get-login-password --region {region} | "
        f"docker login --username AWS --password-stdin {proxy}",
        shell=True, check=True
    )

    click.echo(f"Building Docker image {repository_name}:{tag}...")
    # Build and push Docker image with the docker file path
    image_full_uri = f"{repository_uri}:{tag}"
    subprocess.run([
        "docker", "build",
        "--platform=linux/amd64",
        "-t", image_full_uri,
        "-f", dockerfile_path,
        "."
    ], check=True)
    subprocess.run(f"docker push {image_full_uri}", shell=True, check=True)
    return image_full_uri


def create_s3_bucket(bucket_name, region):
    """
    Function to create an S3 bucket for storing Lambda function code.

    Args:
        bucket_name: str, the name of the S3 bucket to create.
        region: str, the AWS region where the bucket will be created.

    Returns:
        None
    """
    bucket_name = sanitize_bucket_name(bucket_name)
    s3 = boto3.client('s3', region_name=region)
    try:
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': region}
        )
        click.echo(f"Created S3 bucket: {bucket_name}")
    except s3.exceptions.BucketAlreadyExists:
        click.echo(f"S3 bucket {bucket_name} already exists.")


def read_env_file(env_path) -> dict:
    """
    Function to read environment variables from a .env file.

    Args:
        env_path: str, the path to the .env file.

    Returns:
        None
    """
    if not os.path.exists(env_path):
        click.echo(f"No .env file found at {env_path}")
        return {}
    with open(env_path) as f:
        return dict(
            line.strip().split("=", 1)
            for line in f if "=" in line
        )


def check_lambda_permissions(required_actions=None):
    """
    Checks whether the current IAM user/role has the required permissions
    to interact with AWS Lambda. Raises a ClickException if not.

    Args:
        required_actions: List of required IAM actions (strings).
            Default: basic Lambda deploy permissions.

    Raises:
        click.ClickException: If user lacks one or more required permissions.
    """
    if required_actions is None:
        required_actions = [
            "lambda:GetFunction",
            "lambda:UpdateFunctionCode",
            "lambda:UpdateFunctionConfiguration",
            "lambda:CreateFunction",
            "ecr:CreateRepository"
        ]

    sts = boto3.client("sts")
    iam = boto3.client("iam")

    # Get caller identity ARN (could be user or role)
    identity_arn = sts.get_caller_identity()["Arn"]

    # Extract the principal name from the ARN
    if ":user/" in identity_arn:
        principal_type = "user"
        principal_name = identity_arn.split(":user/")[1]
    elif ":role/" in identity_arn:
        principal_type = "role"
        principal_name = identity_arn.split(":role/")[1]
    else:
        raise click.ClickException(
            f"Unsupported identity type: {identity_arn}"
        )

    click.echo(
        f"Checking permissions for IAM {principal_type}: {principal_name}"
    )

    # Simulate the policy and check each required action
    failed_actions = []

    for action in required_actions:
        response = iam.simulate_principal_policy(
            PolicySourceArn=identity_arn,
            ActionNames=[action]
        )
        decision = response["EvaluationResults"][0]["EvalDecision"]

        if decision != "allowed":
            failed_actions.append(action)

    if failed_actions:
        raise click.ClickException(
            f"Your IAM identity '{principal_name}' is missing "
            "required permissions: "
            f"{', '.join(failed_actions)}"
            ". Please ensure you have the necessary permissions "
            "to deploy your trading bot to Lambda functions."
        )


def wait_for_lambda_update(lambda_client, function_name, timeout=60):
    """
    Wait until the Lambda function update completes or times out.

    Args:
        lambda_client: boto3 Lambda client.
        function_name: str, the name of the Lambda function to check.
        timeout: int, maximum time to wait for the
            update (default is 60 seconds).

    Returns:
        None: If the update is successful.
    """
    start = time.time()

    while time.time() - start < timeout:
        response = lambda_client.get_function_configuration(
            FunctionName=function_name
        )
        status = response.get("LastUpdateStatus")
        if status == "Successful":
            return
        elif status == "Failed":
            raise click.ClickException("Previous Lambda update failed.")

        time.sleep(2)

    raise click.ClickException(
        "Timed out waiting for Lambda update to complete."
    )


def command(
    lambda_function_name,
    region,
    project_dir=None,
    memory_size=3000,
    env_vars=None
):
    """
    Command-line tool for deploying a trading bot to AWS Lambda.

    Args:
        lambda_function_name:
        region: str, the AWS region where the Lambda function will be deployed.
        project_dir: str, the directory containing the Lambda function code.
            If None, it defaults to the current directory.
        memory_size: int, the amount of memory allocated
            to the Lambda function

    Returns:
        None
    """
    if project_dir is None:
        # Get the current working directory
        project_dir = os.getcwd()

    check_lambda_permissions()

    click.echo(
        "Deploying to AWS Lambda "
        f"function: {lambda_function_name} in region: {region}"
    )
    click.echo(f"Project directory: {project_dir}")

    # Create s3 bucket for state handler
    bucket_name = f"{lambda_function_name}-state-handler-{region}"
    bucket_name = sanitize_bucket_name(bucket_name)

    if not s3_bucket_exists(bucket_name, region):
        create_s3_bucket(bucket_name, region)

    local_env_vars = read_env_file(
        env_path=os.path.join(project_dir, ".env") if project_dir else ".env"
    )
    if env_vars is None:
        env_vars = {}

    env_vars.update(local_env_vars)

    click.echo("Adding S3 bucket name to environment variables")
    env_vars[AWS_S3_STATE_BUCKET_NAME] = bucket_name

    click.echo("Building and pushing Docker image to ECR")
    create_ecr_repository(lambda_function_name, region)
    image_uri = build_and_push_docker_image(
        lambda_function_name,
        region,
        dockerfile_path=os.path.join(project_dir, "Dockerfile"),
        tag="latest"
    )
    click.echo("Creating IAM role for Lambda execution")
    role_arn = create_iam_role("lambda-execution-role")
    deploy_lambda(
        lambda_function_name,
        image_uri=image_uri,
        role_arn=role_arn,
        env_vars=env_vars,
        region=region,
        memory_size=memory_size
    )
