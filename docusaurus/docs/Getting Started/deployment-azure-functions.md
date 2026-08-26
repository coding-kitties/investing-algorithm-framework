---
sidebar_position: 13
---

# Deploying to Azure Functions

Learn how to deploy your trading algorithm to Azure Functions using the built-in `iaf` CLI, with Blob Storage for state persistence.

## Prerequisites

- Azure CLI installed and authenticated (`az login`), or use `--skip_login` in CI/CD
- Azure Functions Core Tools installed (`npm install -g azure-functions-core-tools@4`)
- Python 3.10+ and the Azure SDK installed (`pip install investing-algorithm-framework[azure]`)

## Scaffolding a Project

Use `iaf init --type azure_function` to generate an Azure Functions-ready project skeleton:

```bash
iaf init --type azure_function
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type` | `default` | Use `azure_function` for this template. |
| `--path` | Current directory | Path to the directory where the project will be created. |
| `--replace` | `False` | If set, existing files will be overwritten. |

### Generated Files

Everything from the default template, plus:

- `function_app.py` — Azure Function entry point
- `host.json` — Azure Functions host configuration
- `local.settings.json` — Local development settings
- `requirements.txt` — Includes Azure SDK dependencies
- `.env.example` — Azure-specific environment variables

## Deploying

The `iaf deploy-azure-function` command deploys your project as an Azure Function App, creating the necessary resource group, storage account, and function app.

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

## Environment Variables

Store exchange API keys and other secrets as environment variables rather than in code. Add them to your `.env` file in the project root — the deploy command reads this file and sets them as Function App configuration:

```bash
# .env
BITVAVO_API_KEY=your_key
BITVAVO_SECRET_KEY=your_secret
```

## Next Steps

With your bot deployed, refer to the [Trading Strategies](strategies) and [Backtesting](backtesting) documentation to refine your algorithms, or head back to the [Going Live overview](deployment).
