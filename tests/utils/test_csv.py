import os
import random
import csv
import pytest

from tests.resources.utils import random_string
from investing_algorithm_framework.utils.csv import remove_row, csv_to_list
from investing_algorithm_framework.core.exceptions import OperationalException


class Test:

    def setup_method(self, test_method):
        # Create temp csv file
        self.csv_path = os.path.join('/tmp', random_string(10) + '.csv')
        os.mknod(self.csv_path)

        records = 200
        fieldnames = ['id', 'name', 'age', 'city']
        names = ['Deepak', 'Sangeeta', 'Geetika', 'Anubhav', 'Sahil', 'Akshay']
        cities = ['Delhi', 'Kolkata', 'Chennai', 'Mumbai']

        # Open file in append mode
        with open(self.csv_path, 'w', newline='') as write_obj:
            # Create a writer object from csv module
            dict_writer = csv.DictWriter(write_obj, fieldnames=fieldnames)

            for i in range(0, records):
                dict_writer.writerow(dict([
                    ('id', i),
                    ('name', random.choice(names)),
                    ('age', str(random.randint(24, 26))),
                    ('city', random.choice(cities))]))

    def teardown_method(self, test_method):

        if os.path.isfile(self.csv_path):
            os.remove(self.csv_path)

    def test_remove_row(self):
        data = csv_to_list(self.csv_path)
        remove_row(self.csv_path, row_index=0)
        new_data = csv_to_list(self.csv_path)

        # Test if the row is removed
        assert data[0] != new_data[0]

        with pytest.raises(OperationalException):
            remove_row(self.csv_path, row_index=-2)

