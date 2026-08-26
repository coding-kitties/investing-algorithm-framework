---
sidebar_position: 12
---

# Deploying to AWS Lambda

Learn how to deploy your trading algorithm to AWS Lambda using the built-in `iaf` CLI, with an S3 bucket for state persistence.

## Prerequisites

- AWS credentials configured (via `aws configure` or environment variables)
- Python 3.10+ and `boto3` installed (`pip install investing-algorithm-framework[aws]`)
- Docker installed (for building the deployment package)

## Scaffolding a Project

Use `iaf init --type aws_lambda` to generate a Lambda-ready project skeleton:

```bash
iaf init --type aws_lambda
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type` | `default` | Use `aws_lambda` for this template. |
| `--path` | Current directory | Path to the directory where the project will be created. |
| `--replace` | `False` | If set, existing files will be overwritten. |

### Generated Files

Everything from the default template, plus:

- `app.py` — Lambda handler entry point
- `Dockerfile` — Container image for Lambda deployment
- `.dockerignore` — Files to exclude from the Docker image
- `requirements.txt` — Includes `boto3` and framework dependencies
- `README.md` — Lambda-specific deployment instructions

## Deploying

The `iaf deploy-aws-lambda` command packages your project, creates (or updates) an AWS Lambda function, and sets up an S3 bucket for state persistence.

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
  -e BITVAVO_SECRET_KEY your_secret
```

## Environment Variables

Store exchange API keys and other secrets as environment variables rather than in code. Pass them with the repeatable `-e` flag during deployment:

```bash
iaf deploy-aws-lambda \
  --lambda_function_name my-bot \
  --region us-east-1 \
  -e BITVAVO_API_KEY your_key \
  -e BITVAVO_SECRET_KEY your_secret
```

## Next Steps

With your bot deployed, refer to the [Trading Strategies](strategies) and [Backtesting](backtesting) documentation to refine your algorithms, or head back to the [Going Live overview](deployment).
