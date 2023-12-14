class MarketCredential:
    def __init__(self, api_key: str, secret_key: str, market: str):
        self._api_key = api_key
        self._secret_key = secret_key
        self._market = market

    def get_api_key(self):
        return self.api_key

    def get_secret_key(self):
        return self.secret_key

    def get_market(self):
        return self.market

    @property
    def market(self):
        return self._market

    @property
    def api_key(self):
        return self._api_key

    @property
    def secret_key(self):
        return self._secret_key
