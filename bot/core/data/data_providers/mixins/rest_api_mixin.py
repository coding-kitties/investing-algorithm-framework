from typing import Dict, Any
import requests
from json.encoder import JSONEncoder


class RequestFactory:

    def __init__(self, api_base: str = None, json_encoder=JSONEncoder):
        self.json_encoder = json_encoder

        if api_base is not None:
            self.api_base = api_base

        self.environment = self.setup_environment()

    def setup_environment(self) -> Dict:
        assert getattr(self, 'api_base'), 'You must define an api base'

        environment = {
            'api_base': getattr(self, 'api_base'),
        }

        return environment

    def get_url(self, endpoint: str, kwargs: Dict[str, any]) -> str:
        """
        Function that will parse a url
        """

        return self.environment.get('api_base') + endpoint.format(kwargs)

    @staticmethod
    def get(url: str, data=None):
        data = {} if data is None else data
        url = url

        return requests.get(url=url, data=data)


class RestApiClientMixin(RequestFactory):
    api_base = None

    def __init__(self):
        super(RestApiClientMixin, self).__init__()
        self._credentials = {}

    @property
    def credentials(self) -> Dict[str, Any]:
        """
        Sets headers that will be used on every outgoing request.
        """
        return self._credentials

    @credentials.setter
    def credentials(self, **kwargs: Dict[str, Any]) -> None:

        self._credentials = kwargs

    @staticmethod
    def get(url: str, data=None):
        response = super().get(url=url, data=data)
        return response






