import csv
import shutil
import tempfile
from typing import Dict, List

from ..exceptions import OperationalException


# Function to add column headers to csv
def add_column_headers_to_csv(file_name: str, column_names: List[str]) -> None:

    # Open file in append mode
    with open(file_name, 'a+', newline='') as write_obj:

        # Create a writer object from csv module
        csv_writer = csv.writer(write_obj)

        # Add the columns
        csv_writer.writerow(column_names)


# Function to append dict as a row to csv
def append_dict_as_row_to_csv(
        file_name: str, dict_data: Dict, field_names: List[str]
) -> None:
    result_dict = {field: dict_data[field] for field in field_names}

    # Open file in append mode
    with open(file_name, 'a', newline='') as write_obj:
        # Create a writer object from csv module
        dict_writer = csv.DictWriter(write_obj, fieldnames=field_names)
        # Add dictionary as wor in the csv
        dict_writer.writerow(result_dict)


def get_total_amount_of_rows(file_path: str):
    file = open(file_path)
    reader = csv.reader(file)
    rows_count = len(list(reader))
    file.close()
    return rows_count


# Function to convert a csv to a list of data_provider
def csv_to_list(csv_path: str, strip_column_headers: bool = False) -> List:
    data = []
    with open(csv_path, "r") as csv_f:
        reader = csv.reader(csv_f, delimiter=',')

        for row in reader:

            if row:  # avoid blank lines
                data.append(row)

    # Delete columns
    if strip_column_headers:
        del data[0]

    return data


# Function to remove a row of a csv corresponding to a particular index
def remove_row(csv_path: str, row_index: int) -> None:

    if row_index < 0:
        raise OperationalException('Negative index number')

    _, temp_file = tempfile.mkstemp(suffix='.csv')

    with open(csv_path, 'r') as inf, open(temp_file, 'w') as out_f:
        writer = csv.writer(out_f)
        index = 0

        for row in csv.reader(inf):

            # Copy every row except the index row
            if index != row_index:
                writer.writerow(row)

            index += 1

    shutil.move(temp_file, csv_path)


def load_csv_into_dict(file_path) -> Dict:
    """
      Load a CSV file into a dictionary.

      Args:
          file_path (str): Path to the CSV file.

      Returns:
          dict: Dictionary containing the data loaded from the CSV file.
      """
    data_dict = {}

    with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
        csv_reader = csv.DictReader(csvfile)

        for row in csv_reader:
            for key, value in row.items():
                data_dict[key] = value

    return data_dict
