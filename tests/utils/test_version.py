from unittest import TestCase
from investing_algorithm_framework.utils.version import get_version, \
    get_complete_version, get_main_version


class TestVersion(TestCase):

    def test(self):

        self.assertIsNotNone(get_version())
        self.assertEqual(type(get_version()), str)

        version = (1, 0, 0, 'alpha', 0)

        self.assertEqual(get_version(version), '1.0')
        self.assertEqual(get_main_version(version), '1.0')
        self.assertEqual(get_complete_version(version), version)


