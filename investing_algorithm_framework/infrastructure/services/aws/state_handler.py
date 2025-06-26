import os
import logging
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from investing_algorithm_framework.domain import OperationalException, \
    StateHandler

logger = logging.getLogger("investing_algorithm_framework")


class AWSS3StorageStateHandler(StateHandler):
    """
    A state handler for AWS S3 storage.

    This class provides methods to save and load state to and from
    AWS S3 storage.

    Attributes:
        bucket_name (str): The name of the AWS S3 bucket.
    """

    def __init__(self, bucket_name: str = None):
        self.bucket_name = bucket_name
        self.s3_client = None

    def initialize(self):
        self.bucket_name = self.bucket_name or os.getenv("AWS_S3_BUCKET_NAME")

        if not self.bucket_name:
            raise OperationalException(
                "AWS S3 state handler requires a bucket name or the "
                "AWS_S3_BUCKET_NAME environment variable to be set."
            )

        self.s3_client = boto3.client("s3")

    def save(self, source_directory: str):
        """
        Save the state to AWS S3.

        Args:
            source_directory (str): Directory to save the state

        Returns:
            None
        """
        logger.info("Saving state to AWS S3 ...")

        try:
            # Walk through the directory
            for root, _, files in os.walk(source_directory):
                for file_name in files:
                    # Get the full path of the file
                    file_path = os.path.join(root, file_name)

                    # Construct the S3 object key (relative path in the bucket)
                    s3_key = os.path.relpath(file_path, source_directory)\
                        .replace("\\", "/")

                    # Upload the file
                    self.s3_client.upload_file(
                        file_path, self.bucket_name, s3_key
                    )

        except (NoCredentialsError, PartialCredentialsError) as ex:
            logger.error(f"Error saving state to AWS S3: {ex}")
            raise OperationalException(
                "AWS credentials are missing or incomplete."
            )
        except Exception as ex:
            logger.error(f"Error saving state to AWS S3: {ex}")
            raise ex

    def load(self, target_directory: str):
        """
        Load the state from AWS S3.

        Args:
            target_directory (str): Directory to load the state

        Returns:
            None
        """
        logger.info("Loading state from AWS S3 ...")

        try:
            # Ensure the local directory exists
            if not os.path.exists(target_directory):
                os.makedirs(target_directory)

            # List and download objects
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name)
            if "Contents" in response:
                for obj in response["Contents"]:
                    s3_key = obj["Key"]
                    file_path = os.path.join(target_directory, s3_key)

                    # Create subdirectories locally if needed
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)

                    # Download object to file
                    self.s3_client.download_file(
                        self.bucket_name, s3_key, file_path
                    )

        except (NoCredentialsError, PartialCredentialsError) as ex:
            logger.error(f"Error loading state from AWS S3: {ex}")
            raise OperationalException(
                "AWS credentials are missing or incomplete."
            )
        except Exception as ex:
            logger.error(f"Error loading state from AWS S3: {ex}")
            raise ex
