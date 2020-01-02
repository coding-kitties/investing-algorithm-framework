import os
import logging
import sqlite3
from sqlite3 import Error
from sys import version_info
from typing import Dict, Any

from bot import settings

logger = logging.getLogger(__name__)

if version_info.major == 3 and version_info.minor < 6 or version_info.major < 3:
    print('Your Python interpreter must be 3.6 or greater!')
    exit(1)


def setup_database(config: Dict[str, Any]) -> None:
    database_name = config.get('database', {}).get('name', 'bot_configuration')
    data_base_file = os.path.join(settings.PARENT_DIR, '{}.db'.format(database_name))

    logger.info("Database {} is initialized ...".format(database_name))

    if not os.path.isfile(data_base_file):

        logger.info("Database is being created ...")
        try:
            conn = sqlite3.connect(data_base_file)
        except Error as e:
            logger.error(e)
        finally:
            if conn:
                conn.close()


def get_database_file(config: Dict[str, Any]) -> str:
    database_name = config.get('database', {}).get('name', 'bot_configuration')
    return os.path.join(settings.PARENT_DIR, '{}.db'.format(database_name))
