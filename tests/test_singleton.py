from bot.utils import Singleton


class DummySingleton(metaclass=Singleton):
    pass


def test():
    dummy_one = DummySingleton()
    dummy_two = DummySingleton()

    assert dummy_one == dummy_two

