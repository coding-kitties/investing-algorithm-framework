class ImproperlyConfigured(Exception):
    """
    Class ImproperlyConfigured: Exception class indicating a problem with the configuration of the investing_bot_framework
    """
    def __init__(self, message) -> None:
        super(ImproperlyConfigured, self).__init__(message)


class OperationalException(Exception):
    """
    Class OperationalException: Exception class indicating a problem occurred during running of the investing_bot_framework
    """
    def __init__(self, message) -> None:
        super(OperationalException, self).__init__(message)
