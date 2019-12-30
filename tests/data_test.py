import logging
import requests
import pandas as pd
from pandas import DataFrame
from pandas.io.json import json_normalize

from bot.data.data_providers.data_provider import DataProvider

TICKER_LIST = 'https://financialmodelingprep.com/api/v3/company/stock/list'
PROFILE_ENDPOINT = 'https://financialmodelingprep.com/api/v3/company/profile/{}'

logger = logging.getLogger(__name__)


PROFILE_COLUMNS = [
    'price',
    'beta',
    'volAvg',
    'mktCap',
    'lastDiv',
    'range',
    'changes',
    'changePercentage',
    'companyName',
    'exchange',
    'industry',
    'website',
    'description',
    'ceo',
    'sector',
    'image',
    'symbol'
]


class DummyFMPDataProvider(DataProvider):

    def __init__(self):
        super(DummyFMPDataProvider, self).__init__()
        self._id = "FINANCIAL_MODELING_PREP_PROVIDER"

    def get_id(self) -> str:
        return self._id

    def provide_data(self) -> DataFrame:
        data = requests.get(TICKER_LIST).json()
        df = json_normalize(data['symbolsList'])

        profile_df = DataFrame(columns=PROFILE_COLUMNS)

        rows = df.iloc[[0, 10]]

        for index, row in rows.iterrows():

            symbol = row['symbol']

            profile_data = requests.get(PROFILE_ENDPOINT.format(symbol)).json()
            profile_data = json_normalize(profile_data['profile'])
            profile_data['symbol'] = symbol

            profile_df.append(profile_data)

        rows.append(profile_df)
        # merged_df = pd.merge(
        #     rows.set_index('symbol'),
        #     profile_df.set_index('symbol'),
        #     how='left',
        #     left_index=True,
        #     right_index=True
        # )
        #
        # logger.info(merged_df)
        logger.info(rows)
        return rows


def test_fmp():

    dummy = DummyFMPDataProvider()

    dummy.start()

