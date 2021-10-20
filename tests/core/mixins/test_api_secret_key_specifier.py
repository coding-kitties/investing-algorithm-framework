from investing_algorithm_framework.core.mixins \
    import BinanceApiSecretKeySpecifierMixin
from tests.resources import TestBase, random_string


class MySpecifier(BinanceApiSecretKeySpecifierMixin):
    binance_api_key = random_string(5)
    binance_secret_key = random_string(5)


class Test(TestBase):

    def test(self):
        test_object = MySpecifier()
        self.assertIsNotNone(test_object.get_api_key())
        self.assertIsNotNone(test_object.get_secret_key())
