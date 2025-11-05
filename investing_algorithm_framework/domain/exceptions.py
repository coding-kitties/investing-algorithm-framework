class ApiException(Exception):

    def __init__(self, message: str = None, status_code: int = 400):
        super(ApiException, self).__init__(message)
        self._message = message
        self._status_code = status_code

    @property
    def error_message(self):

        if self._message is None:
            return "An error occurred"

        return self._message

    @property
    def status_code(self):

        if self._status_code is None:
            return 500

        return self._status_code


class PermissionDeniedApiException(ApiException):

    def __init__(self):
        super(PermissionDeniedApiException, self).__init__(
            message="Permission denied", status_code=401
        )


class ImproperlyConfigured(Exception):
    """
    Class ImproperlyConfigured: Exception class indicating a problem with
    the configuration of the investing_algorithm_framework
    """
    def __init__(self, message) -> None:
        super(ImproperlyConfigured, self).__init__(message)
        self.error_message = message

    def to_response(self):
        return {
            "status": "error",
            "message": self.error_message
        }


class OperationalException(Exception):
    """
    Class OperationalException: Exception class indicating a problem occurred
    during running of the investing_algorithm_framework.

    This exception is used to indicate that an error occurred during the
    operation of the investing_algorithm_framework, such as during a backtest,
    strategy execution, or any other operational aspect of the framework.

    Attributes:
        message (str): The error message to be returned in the response.
    """
    def __init__(self, message) -> None:
        super(OperationalException, self).__init__(message)
        self.error_message = message

    def to_response(self):
        return {
            "status": "error",
            "message": self.error_message
        }


class NetworkError(Exception):
    """
    Class NetworkError: Exception class indicating a problem occurred
    during making a netwok request
    """

    def __init__(self, message) -> None:
        super(NetworkError, self).__init__(message)
        self.error_message = message

    def to_response(self):
        return {
            "status": "error",
            "message": self.error_message
        }


class DataError(Exception):
    """
    Class DataError: Exception class indicating a problem occurred
    during data retrieval or processing
    """

    def __init__(
        self,
        message,
        data_source_file_path: str = None,
        number_of_missing_data_points: int = None,
        total_number_of_data_points: int = None,
    ) -> None:
        super(DataError, self).__init__(message)
        self.error_message = message
        self.data_source_file_path = data_source_file_path
        self.number_of_missing_data_points = number_of_missing_data_points
        self.total_number_of_data_points = total_number_of_data_points

    def to_response(self):
        return {
            "status": "error",
            "message": self.error_message
        }
