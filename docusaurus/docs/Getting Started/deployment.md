---
sidebar_position: 11
---

# Deployment

Learn how to deploy your trading algorithms to AWS Lambda or Azure Functions using the built-in CLI.

## Overview

The Investing Algorithm Framework includes a CLI tool (`iaf`) that handles scaffolding and deployment to cloud platforms. Two deployment targets are supported out of the box:

- **AWS Lambda** — Serverless deployment using boto3, with an S3 bucket for state persistence.
- **Azure Functions** — Serverless deployment using the Azure SDK, with blob storage for state persistence.

## Scaffolding a Project

Use `iaf init` to generate a project skeleton for your chosen deployment target:

```bash
# Default project (local execution)
iaf init

# Project with a web interface
iaf init --type default_web

# AWS Lambda project
iaf init --type aws_lambda

# Azure Function project
iaf init --type azure_function
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type` | `default` | Project type: `default`, `default_web`, `aws_lambda`, or `azure_function`. |
| `--path` | Current directory | Path to the directory where the project will be created. |
| `--replace` | `False` | If set, existing files will be overwritten. |

Each template generates the appropriate entry point, requirements file, configuration files, and deployment scaffolding for the chosen platform.

## Deploying to AWS Lambda

The `iaf deploy-aws-lambda` command packages your project, creates (or updates) an AWS Lambda function, and sets up an S3 bucket for state persistence.

### Prerequisites

- AWS credentials configured (via `aws configure` or environment variables)
- Python 3.10+ and `boto3` installed
- Docker installed (for building the deployment package)

### Command

```bash
iaf deploy-aws-lambda \
  --lambda_function_name my-trading-bot \
  --region us-east-1
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--lambda_function_name` | Yes | — | Name of the Lambda function to create or update. |
| `--region` | Yes | — | AWS region (e.g., `us-east-1`, `eu-west-1`). |
| `--project_dir` | No | Current directory | Path to the project directory containing your code. |
| `--memory_size` | No | `3000` | Memory allocation in MB for the Lambda function. |
| `-e KEY VALUE` | No | — | Environment variables. Can be repeated: `-e API_KEY xxx -e SECRET yyy`. |

### What It Does

1. Packages your project code into a deployment zip.
2. Creates an IAM role for Lambda execution (if it doesn't exist).
3. Creates an S3 bucket for state storage (named after the function).
4. Deploys the Lambda function with the specified memory and environment variables.
5. Sets the `AWS_S3_STATE_BUCKET_NAME` environment variable on the function automatically.

### Example

```bash
# Deploy with environment variables for exchange credentials
iaf deploy-aws-lambda \
  --lambda_function_name btc-trading-bot \
  --region eu-west-1 \
  --memory_size 3000 \
  -e BITVAVO_API_KEY your_key \
  -e BITVAVO_API_SECRET your_secret
```

## Deploying to Azure Functions

The `iaf deploy-azure-function` command deploys your project as an Azure Function App, creating the necessary resource group, storage account, and function app.

### Prerequisites

- Azure CLI installed and authenticated (`az login`), or use `--skip_login` in CI/CD
- Azure Functions Core Tools installed (`npm install -g azure-functions-core-tools@4`)
- Python 3.10+

### Command

```bash
iaf deploy-azure-function \
  --resource_group my-resource-group \
  --deployment_name my-trading-bot \
  --region westeurope
```

### Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--resource_group` | Yes | — | Azure resource group name. |
| `--deployment_name` | Yes | — | Name for the Function App. |
| `--region` | Yes | — | Azure region (e.g., `westeurope`, `eastus`). |
| `--subscription_id` | No | Default subscription | Azure subscription ID. |
| `--storage_account_name` | No | Auto-generated | Name for the Azure Storage account. |
| `--container_name` | No | `iafcontainer` | Blob container name for state storage. |
| `--create_resource_group_if_not_exists` | No | `False` | Create the resource group if it doesn't exist. |
| `--skip_login` | No | `False` | Skip `az login` (useful for CI/CD pipelines). |

### What It Does

1. Verifies Azure Functions Core Tools are installed.
2. Creates the resource group (if `--create_resource_group_if_not_exists` is set).
3. Creates or reuses a storage account and blob container for state.
4. Deploys the Function App using Azure Functions Core Tools.
5. Reads `.env` file from your project directory and sets those values as Function App configuration.

### Example

```bash
# Deploy with a new resource group
iaf deploy-azure-function \
  --resource_group trading-bots-rg \
  --deployment_name btc-trader \
  --region westeurope \
  --create_resource_group_if_not_exists
```

## Project Templates

When you run `iaf init`, the framework generates different files depending on the `--type`:

### Default (`default`)

- `app.py` — Main entry point with `create_app()` and `app.start()`
- `strategy.py` — Example `TradingStrategy` subclass
- `data_providers.py` — Example data provider setup
- `requirements.txt` — Python dependencies
- `.env.example` — Template for environment variables
- `.gitignore` — Standard Python gitignore

### AWS Lambda (`aws_lambda`)

Everything from `default`, plus:
- `app.py` — Lambda handler entry point
- `Dockerfile` — Container image for Lambda deployment
- `.dockerignore` — Files to exclude from the Docker image
- `requirements.txt` — Includes `boto3` and framework dependencies
- `README.md` — Lambda-specific deployment instructions

### Azure Function (`azure_function`)

Everything from `default`, plus:
- `function_app.py` — Azure Function entry point
- `host.json` — Azure Functions host configuration
- `local.settings.json` — Local development settings
- `requirements.txt` — Includes Azure SDK dependencies
- `.env.example` — Azure-specific environment variables

## Environment Variables

Both deployment targets support environment variables for sensitive configuration. Store exchange API keys and other secrets as environment variables rather than in code.

For **AWS Lambda**, use the `-e` flag during deployment:

```bash
iaf deploy-aws-lambda \
  --lambda_function_name my-bot \
  --region us-east-1 \
  -e BITVAVO_API_KEY your_key \
  -e BITVAVO_API_SECRET your_secret
```

For **Azure Functions**, add variables to your `.env` file in the project root. The deploy command reads this file and sets them as Function App configuration:

```bash
# .env
BITVAVO_API_KEY=your_key
BITVAVO_API_SECRET=your_secret
```

## Next Steps

With your bot deployed, refer to the [Trading Strategies](strategies) and [Backtesting](backtesting) documentation to refine your algorithms before going live.
