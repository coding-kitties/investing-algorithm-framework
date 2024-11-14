# import os
# import json
# from azure.identity import DefaultAzureCredential
# from azure.mgmt.resource import ResourceManagementClient
# from azure.mgmt.storage import StorageManagementClient
# from azure.mgmt.web import WebSiteManagementClient
# import shutil


# def deploy_to_azure_functions(azure_credentials_json, azure_function_path):
#     """
#     This function deploys a Python function app to Azure Functions.

#     Parameters:
#         - azure_credentials_json (str): Path to the Azure credentials
#         JSON file.
#         - azure_function_path (str): Path to the Python function
#         app directory.

#     Returns:
#         None
#     """

#     # Load Azure credentials
#     with open('azure_credentials.json') as f:
#         credentials = json.load(f)

#     SUBSCRIPTION_ID = credentials['subscriptionId']
#     RESOURCE_GROUP_NAME = "myResourceGroup"
#     LOCATION = "eastus"
#     STORAGE_ACCOUNT_NAME = "mystorageaccount123"
#     FUNCTION_APP_NAME = "my-python-function-app"

#     # Authenticate using DefaultAzureCredential
#     credential = DefaultAzureCredential()

#     # Clients
#     resource_client = ResourceManagementClient(credential, SUBSCRIPTION_ID)
#     storage_client = StorageManagementClient(credential, SUBSCRIPTION_ID)
#     web_client = WebSiteManagementClient(credential, SUBSCRIPTION_ID)

#     # Create Resource Group
#     resource_client.resource_groups.create_or_update(RESOURCE_GROUP_NAME,
#                                                      {"location": LOCATION})

#     # Create Storage Account
#     storage_client.storage_accounts.begin_create(
#         RESOURCE_GROUP_NAME,
#         STORAGE_ACCOUNT_NAME,
#         {
#             "sku": {"name": "Standard_LRS"},
#             "kind": "StorageV2",
#             "location": LOCATION
#         }
#     ).result()

#     # Create Function App (with a Consumption Plan)
#     site_config = {
#         "location": LOCATION,
#         "server_farm_id": f"/subscriptions/{SUBSCRIPTION_ID}" +
#         "/resourceGroups" +
#         "/{RESOURCE_GROUP_NAME}/providers/Microsoft.Web/" +
#         "serverfarms/{APP_SERVICE_PLAN_NAME}",
#         "reserved": True,  # This is necessary for Linux-based function apps
#         "site_config": {
#             "app_settings": [
#                 {
#                     "name": "FUNCTIONS_WORKER_RUNTIME", "value": "python"
#                 },
#                 {
#                     "name": "AzureWebJobsStorage",
#                     "value": "DefaultEndpointsProtocol=https;" +
#                     f"AccountName={STORAGE_ACCOUNT_NAME}" +
#                     ";AccountKey=account_key>",
#                 }
#             ]
#         },
#         "kind": "functionapp",
#     }

#     web_client.web_apps.begin_create_or_update(RESOURCE_GROUP_NAME,
#                                                FUNCTION_APP_NAME,
#                                                site_config).result()

#     # Zip Function Code
#     def zipdir(path, zipfile):
#         for root, dirs, files in os.walk(path):
#             for file in files:
#                 zipfile.write(os.path.join(root, file),
#                               os.path.relpath(os.path.join(root, file), path))

#     shutil.make_archive('myfunctionapp', 'zip', 'myfunctionapp/')

#     # Deploy Function Code
#     def deploy_function():
#         with open("myfunctionapp.zip", "rb") as z:
#             web_client.web_apps.begin_create_zip_deployment(
#                 RESOURCE_GROUP_NAME, FUNCTION_APP_NAME, z).result()

#     deploy_function()

#     print(f"Function app '{FUNCTION_APP_NAME}' deployed to Azure.")
