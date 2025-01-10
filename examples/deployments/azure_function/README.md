# Investing Algorithm Framework App Deployment to Azure Functions

This article demonstrates how to deploy your trading bot to Azure Functions.
We will deploy an example bot that uses the investing algorithm framework to
azure functions. In order to do that we will do the following:

1. Create a new app using the framework with the azure blob storage state handler.
2. Use the framework provided ci tools to create a azure functions ready application.
3. Use the framework provided ci tools to deploy the application to azure functions.

## Prerequisites

For this example, you need to have the following:

- An Azure account with an active subscription. [Create an account](https://azure.microsoft.com/en-us/free/)
- The Azure CLI installed. [Install the Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
- The Azure Functions Core Tools installed. [Install the Azure Functions Core Tools](https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local)
- The investing algorithm framework installed. [Install the framework]() or simply run `pip install investing_algorithm_framework`

### Creating a new app

First run the following command to create a new app azure functions ready app:

```bash
create_azure_function_trading_bot_app
```

This command will create a new app with the following structure:

```yaml
.
├── function_app.py
├── host.json
├── local.settings.json
└── requirements.txt
```

The function_app.py while import the app from the app.py file in the root of the project and run it as an azure function. It is therefore important that you have a file named `app.py` in the root of your project that defines the application in a variable named `app`.

Additionaly, because Azure Functions are stateless, you need to use a state storage solution. In this example, we will use Azure Blob Storage state handler provided by the framework. This state handler is specifically designed to work with Azure Functions and Azure Blob Storage.

The reason why we need a state storage solution is that Azure Functions are stateless. This means that each function execution is independent of the previous one. This is a problem for trading bots because they need to keep track of their state between executions (portfolios, order, positions and trades). In order to solve this problem, we need to use a state storage solution that can store the bot's databases between executions.

Combining all of this, the `app.py` file should look like this:

> When you are using the cli command 'deploy_trading_bot_to_azure_function' (which we will use later) you don't need to provide any connection strings. The command will take care of provisioning all
> resourses and configuration of all required parameters for the state handler.

```python
from investing_algorithm_framework import AzureBlobStorageStateHandler, create_app

app = create_app(state_handler=AzureBlobStorageStateHandler)

# Write here your code where your register your portfolio configurations, strategies and data providers
....
```

## Deployment to Azure

To deploy your trading bot to Azure Functions, you need to run the following command:

```bash
deploy_trading_bot_to_azure_function
```

This command will do the following:

- Create a new resource group in your Azure account.
- Create a new storage account in the resource group.
- Create a new blob container in the storage account.
- Create a new function app in the resource group.
- Deploy the trading bot to the function app.
- Configure the function app to use the blob container as the state handler.
- Print the URL of the function app.

After running the command, you will see the URL of the function app. You can use this URL to access your trading bot. Now your trading bot is running on Azure Functions!
