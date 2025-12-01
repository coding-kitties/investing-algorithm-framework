import os
import logging
import boto3
import stat
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from investing_algorithm_framework.domain import OperationalException, \
    StateHandler

logger = logging.getLogger("investing_algorithm_framework")


def _fix_permissions(target_directory: str):
    """
    Fix permissions on downloaded files to make them writable.

    Args:
        target_directory (str): Directory to fix permissions for
    """
    try:
        # Fix the target directory itself
        os.chmod(target_directory, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

        # Recursively fix all subdirectories and files
        for root, dirs, files in os.walk(target_directory):
            # Fix current directory permissions
            os.chmod(root, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

            # Fix all subdirectories
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                os.chmod(dir_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

            # Fix all files - make them readable and writable
            for file_name in files:
                file_path = os.path.join(root, file_name)
                os.chmod(
                    file_path,
                    stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
                )

        logger.info(f"Update permissions for {target_directory}")
    except Exception as e:
        logger.warning(f"Error fixing permissions: {e}")


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
                "AWS S3 state handler requires a bucket_name para or the "
                "AWS_S3_BUCKET_NAME environment variable needs to be set "
                "in the environment."
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
                    s3_key = os.path.relpath(file_path, source_directory)
                    # Convert to forward slashes for S3 compatibility
                    s3_key = s3_key.replace(os.sep, "/")

                    self.s3_client.upload_file(
                        file_path,
                        self.bucket_name,
                        s3_key,
                        ExtraArgs={'ACL': 'private'}
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
        """
        logger.info("Loading state from AWS S3 ...")

        try:
            if not os.path.exists(target_directory):
                os.makedirs(
                    target_directory,
                    mode=stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
                )

            os.chmod(
                target_directory, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
            )

            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name)

            if "Contents" in response:
                for obj in response["Contents"]:
                    s3_key = obj["Key"]
                    # Convert S3 forward slashes to OS-specific separators
                    file_path = os.path.join(
                        target_directory, s3_key.replace("/", os.sep)
                    )

                    os.makedirs(
                        os.path.dirname(file_path),
                        exist_ok=True,
                        mode=stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
                    )

                    self.s3_client.download_file(
                        self.bucket_name, s3_key, file_path
                    )

                    if os.path.isfile(file_path):
                        os.chmod(
                            file_path,
                            stat.S_IRUSR |
                            stat.S_IWUSR |
                            stat.S_IRGRP |
                            stat.S_IROTH
                        )
                    else:
                        os.chmod(
                            file_path,
                            stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
                        )

            # Final recursive fix
            _fix_permissions(target_directory)

            # Add write permission to database file
            db_file = os.path.join(
                target_directory, "databases", "prod-database.sqlite3"
            )
            if os.path.exists(db_file):
                os.chmod(
                    db_file,
                    stat.S_IRUSR |
                    stat.S_IWUSR |
                    stat.S_IRGRP |
                    stat.S_IWGRP |
                    stat.S_IROTH |
                    stat.S_IWOTH
                )
                logger.info(
                    f"Database file permissions "
                    f"after fix: {oct(os.stat(db_file).st_mode)}"
                )

        except (NoCredentialsError, PartialCredentialsError) as ex:
            logger.error(f"Error loading state from AWS S3: {ex}")
            raise OperationalException(
                "AWS credentials are missing or incomplete."
            )
        except Exception as ex:
            logger.error(f"Error loading state from AWS S3: {ex}")
            raise ex
