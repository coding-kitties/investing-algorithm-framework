---
slug: how-to-deploy-a-trading-bot
title: How to deploy a trading bot
authors:
  name: Marc van Duyn
  title: How to deploy a trading bot
  url: https://github.com/mduyn
  image_url: https://github.com/mduyn.png
tags: [trading bot, deployment, azure functions, aws lambda, crypto, investing algorithm, investing algorithm framework]
---

Once you've built and backtested a strategy (see [How to build a trading bot in 5 steps](/blog/how-to-create-a-trading-bot-in-5-steps)),
the last step is running it somewhere that isn't your laptop. The Investing Algorithm Framework ships a CLI
(`iaf`) that scaffolds and deploys your bot to either **AWS Lambda** or **Azure Functions** — both serverless,
both billed per execution, and both a good fit for a bot that only needs to wake up every few hours to check
the market.

## Before you deploy

This post assumes you already have a working strategy, structured as described in
[Application Setup](/docs/Getting%20Started/application-setup) (an `app.py` importing a `strategies/` package).
If you don't yet, start with [How to build a trading bot in 5 steps](/blog/how-to-create-a-trading-bot-in-5-steps).

## Scaffold a deployment project

`iaf init` generates the entry point, requirements file, and deployment scaffolding for your chosen platform:

```bash
# AWS Lambda project
iaf init --type aws_lambda --path ./my-trading-bot

# Azure Function project
iaf init --type azure_function --path ./my-trading-bot
```

Each template gives you a working skeleton — copy your `strategy.py` from your existing project into the
generated `strategies/` package, and fill in your exchange API keys in the generated `.env`/`.env.example` file.

## Deploying to AWS Lambda

**Prerequisites:** AWS credentials configured (`aws configure`), `boto3` installed, and Docker installed (used to
build the deployment package).

```bash
iaf deploy-aws-lambda \
  --lambda_function_name btc-trading-bot \
  --region eu-west-1 \
  --memory_size 3000 \
  -e BITVAVO_API_KEY your_key \
  -e BITVAVO_API_SECRET your_secret
```

This one command packages your project into a deployment zip, creates an IAM role for Lambda execution (if one
doesn't already exist), creates an S3 bucket for state persistence, and deploys the function with the memory and
environment variables you specified.

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--lambda_function_name` | Yes | — | Name of the Lambda function to create or update. |
| `--region` | Yes | — | AWS region (e.g., `us-east-1`, `eu-west-1`). |
| `--memory_size` | No | `3000` | Memory allocation in MB. |
| `-e KEY VALUE` | No | — | Environment variables; repeat for each one. |

## Deploying to Azure Functions

**Prerequisites:** Azure CLI installed and logged in (`az login`), Azure Functions Core Tools installed
(`npm install -g azure-functions-core-tools@4`).

```bash
iaf deploy-azure-function \
  --resource_group trading-bots-rg \
  --deployment_name btc-trader \
  --region westeurope \
  --create_resource_group_if_not_exists
```

This creates the resource group (if requested), sets up a storage account and blob container for state, reads
your `.env` file and applies its contents as Function App configuration, and deploys the Function App via the
Azure Functions Core Tools.

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `--resource_group` | Yes | — | Azure resource group name. |
| `--deployment_name` | Yes | — | Name for the Function App. |
| `--region` | Yes | — | Azure region (e.g., `westeurope`, `eastus`). |
| `--create_resource_group_if_not_exists` | No | `False` | Create the resource group if it doesn't exist. |

For Azure, store secrets in a `.env` file in the project root rather than passing them on the command line:

```bash
# .env
BITVAVO_API_KEY=your_key
BITVAVO_SECRET_KEY=your_secret
```

## Which one should you pick?

Both work well for a bot that runs on a schedule rather than continuously:

- **AWS Lambda** if your infrastructure is already on AWS, or you want the deployment package built into a
  Docker image (useful if your strategy has heavier dependencies).
- **Azure Functions** if your infrastructure is already on Azure, or you prefer the Azure Functions Core Tools
  workflow for local testing before deploying.

Either way, the same strategy code runs unchanged — the framework's live-trading loop (`app.run()`) is what
gets invoked on a timer trigger in both cases, so what you backtested locally is exactly what runs in the cloud.

See [Deployment](/docs/Getting%20Started/deployment) in the docs for the full CLI reference, including the
project templates each `iaf init --type` generates and how environment variables are handled for each platform.
