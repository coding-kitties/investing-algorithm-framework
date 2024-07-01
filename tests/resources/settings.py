from pathlib import Path

BASE_DIR = str(Path(__file__).parent.parent)

DATABASE_CONFIG = {
    'DATABASE_TYPE': 'sqlite3',
    'DATABASE_NAME': 'test_db',
    'DATABASE_DIRECTORY_PATH': BASE_DIR
}
