class ImproperlyConfigured(Exception):
    """
    Class ImproperlyConfigured: Exception class indicating a problem with
    the configuration of the investing_algorithm_framework
    """
    def __init__(self, message) -> None:
        super(ImproperlyConfigured, self).__init__(message)


class OperationalException(Exception):
    """
    Class OperationalException: Exception class indicating a problem occurred
    during running of the investing_algorithm_framework
    """
    def __init__(self, message) -> None:
        super(OperationalException, self).__init__(message)


class DatabaseOperationalException(Exception):
    """
    Class DatabaseOperationalException: Exception class indicating a problem
    occurred during usage of the database
    """
    def __init__(self, message) -> None:
        super(DatabaseOperationalException, self).__init__(message)
