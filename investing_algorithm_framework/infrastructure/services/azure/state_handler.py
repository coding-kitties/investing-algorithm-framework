import os
import logging

from azure.storage.blob import ContainerClient
from investing_algorithm_framework.domain import OperationalException, \
    StateHandler

logger = logging.getLogger("investing_algorithm_framework")


class AzureBlobStorageStateHandler(StateHandler):
    """
    A state handler for Azure Blob Storage.

    This class provides methods to save and load state to and from
    Azure Blob Storage.

    Attributes:
        connection_string (str): The connection string for Azure Blob Storage.
        container_name (str): The name of the Azure Blob Storage container.
    """

    def __init__(
        self, connection_string: str = None, container_name: str = None
    ):
        self.connection_string = connection_string
        self.container_name = container_name

    def initialize(self):
        """
        Internal helper to initialize the state handler.
        """

        if self.connection_string is None:

            # Check if environment variable is set
            self.connection_string = \
                os.getenv("AZURE_STORAGE_CONNECTION_STRING")

            if self.connection_string is None:
                raise OperationalException(
                    "Azure Blob Storage state handler requires" +
                    " a connection string or an environment" +
                    " variable AZURE_STORAGE_CONNECTION_STRING to be set."
                )

        if self.container_name is None:

            # Check if environment variable is set
            self.container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

            if self.container_name is None:
                raise OperationalException(
                    "Azure Blob Storage state handler requires a" +
                    " container name or an environment" +
                    " variable AZURE_STORAGE_CONTAINER_NAME to be set."
                )

    def save(self, source_directory: str):
        """
        Save the state to Azure Blob Storage.

        Parameters:
            source_directory (str): Directory to save the state

        Returns:
            None
        """
        logger.info("Saving state to Azure Blob Storage ...")

        try:
            container_client = self._create_container_client()

            # Create container if it does not exist
            if not container_client.exists():
                container_client.create_container()

            # Walk through the directory
            for root, _, files in os.walk(source_directory):
                for file_name in files:
                    # Get the full path of the file
                    file_path = os.path.join(root, file_name)

                    # Construct the blob name (relative path in the container)
                    blob_name = os.path.relpath(file_path, source_directory)\
                        .replace("\\", "/")

                    # Upload the file
                    with open(file_path, "rb") as data:
                        container_client.upload_blob(
                            name=blob_name, data=data, overwrite=True
                        )

        except Exception as ex:
            logger.error(f"Error saving state to Azure Blob Storage: {ex}")
            raise ex

    def load(self, target_directory: str):
        """
        Load the state from Azure Blob Storage.

        Parameters:
            target_directory (str): Directory to load the state

        Returns:
            None
        """
        logger.info("Loading state from Azure Blob Storage ...")

        try:
            container_client = self._create_container_client()

            # Ensure the local directory exists
            if not os.path.exists(target_directory):
                os.makedirs(target_directory)

            # List and download blobs
            for blob in container_client.list_blobs():
                blob_name = blob.name
                blob_file_path = os.path.join(target_directory, blob_name)

                # Create subdirectories locally if needed
                os.makedirs(os.path.dirname(blob_file_path), exist_ok=True)

                # Download blob to file
                with open(blob_file_path, "wb") as file:
                    blob_client = container_client.get_blob_client(blob_name)
                    file.write(blob_client.download_blob().readall())

        except Exception as ex:
            logger.error(f"Error loading state from Azure Blob Storage: {ex}")
            raise ex

    def _create_container_client(self):
        """
        Internal helper to create a Container clinet.

        Returns:
            ContainerClient
        """

        # Ensure the container exists
        try:
            container_client = ContainerClient.from_connection_string(
                conn_str=self.connection_string,
                container_name=self.container_name
            )
            container_client.create_container(timeout=10)
        except Exception as e:

            if "ContainerAlreadyExists" in str(e):
                pass
            else:
                raise OperationalException(
                    f"Error occurred while creating the container: {e}"
                )

        return container_client
