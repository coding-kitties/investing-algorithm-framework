# import os
# import random
# import csv
# from unittest import TestCase
#
# from tests.resources.utils import random_string
# from investing_algorithm_framework.utils.csv import remove_row, csv_to_list,\
#     append_dict_as_row_to_csv, get_total_amount_of_rows
# from investing_algorithm_framework.core.exceptions
# import OperationalException
#
#
# class Test(TestCase):
#
#     def setUp(self) -> None:
#         # Create temp csv file
#         self.csv_path = os.path.join('/tmp', random_string(10) + '.csv')
#         open(self.csv_path, 'w').close()
#
#         records = 200
#         fieldnames = ['id', 'name', 'age', 'city']
#         names = ['Deepak', 'Sangeeta',
#         'Geetika', 'Anubhav', 'Sahil', 'Akshay']
#         cities = ['Delhi', 'Kolkata', 'Chennai', 'Mumbai']
#
#         # Open file in append mode
#         with open(self.csv_path, 'w', newline='') as write_obj:
#             # Create a writer object from csv module
#             dict_writer = csv.DictWriter(write_obj, fieldnames=fieldnames)
#
#             for i in range(0, records):
#                 dict_writer.writerow(dict([
#                     ('id', i),
#                     ('name', random.choice(names)),
#                     ('age', str(random.randint(24, 26))),
#                     ('city', random.choice(cities))]))
#
#     def tearDown(self) -> None:
#
#         if os.path.isfile(self.csv_path):
#             os.remove(self.csv_path)
#
#     def test_remove_row(self):
#         data = csv_to_list(self.csv_path)
#         remove_row(self.csv_path, row_index=0)
#         new_data = csv_to_list(self.csv_path)
#
#         # Test if the row is removed
#         assert data[0] != new_data[0]
#
#         with self.assertRaises(OperationalException):
#             remove_row(self.csv_path, row_index=-2)
#
#     def test_append_dict_as_row(self):
#
#         self.assertEqual(200, get_total_amount_of_rows(self.csv_path))
#         data = {
#             'id': 20,
#             'name': "hello",
#             'age': "age",
#             'city': "amsterdam"
#         }
#
#         append_dict_as_row_to_csv(
#             self.csv_path, data, ['id', 'name', 'age', 'city']
#         )
#         self.assertEqual(201, get_total_amount_of_rows(self.csv_path))
#
#         data = {
#             'id': 20,
#             'name': "hello",
#             'age': "age",
#         }
#
#         append_dict_as_row_to_csv(
#             self.csv_path, data, ['id', 'name', 'age']
#         )
#
#         self.assertEqual(202, get_total_amount_of_rows(self.csv_path))
