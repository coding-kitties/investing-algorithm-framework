from wrapt import synchronized


class Singleton(type):
    """
    Class Singleton: lets an instance that extends this class function as a Singleton.
    Only use this in a necessarily case.
    """

    _instances = {}

    @synchronized
    def __call__(cls, *args, **kwargs):

        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)

        return cls._instances[cls]
