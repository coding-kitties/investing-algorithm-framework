from datetime import datetime, timedelta
from unittest import TestCase
from dateutil.tz import tzutc
import pandas as pd
import os

from investing_algorithm_framework.domain import Trade
from investing_algorithm_framework import CSVOHLCVMarketDataSource, \
    CSVTickerMarketDataSource


class Test(TestCase):

    def test_trade(self):
        trade_opened_at = datetime(2023, 11, 29)
        trade = Trade(
            buy_order_id=1,
            target_symbol="BTC",
            trading_symbol="EUR",
            amount=1,
            open_price=19822.0,
            opened_at=trade_opened_at,
            closed_price=None,
            closed_at=None,
        )
        self.assertEqual(trade.target_symbol, "BTC")
        self.assertEqual(trade.trading_symbol, "EUR")
        self.assertEqual(trade.amount, 1)
        self.assertEqual(trade.open_price, 19822.0)
        self.assertEqual(trade.opened_at, trade_opened_at)

    def test_stop_loss_manual(self):
        current_datetime = datetime(2023, 8, 26, 00, 00, 0, tzinfo=tzutc())
        resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.join(
                            os.path.realpath(__file__),
                            os.pardir
                        ),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )
        csv_ohlcv_market_data_source = CSVOHLCVMarketDataSource(
            identifier="BTC",
            market="BITVAVO",
            symbol="BTC/EUR",
            timeframe="15m",
            start_date=current_datetime - timedelta(days=17),
            end_date=current_datetime,
            csv_file_path=f"{resource_dir}/"
                          "market_data_sources/"
                          "OHLCV_BTC-EUR_BINANCE_2h_2023-08-07:07"
                          ":59_2023-12-02:00:00.csv"
        )
        csv_ticker_market_data_source = CSVTickerMarketDataSource(
            identifier="BTC",
            market="BITVAVO",
            symbol="BTC/EUR",
            csv_file_path=f"{resource_dir}"
                          "/market_data_sources/"
                          "TICKER_BTC-EUR_BINANCE_2023-08"
                          "-23:22:00_2023-12-02:00:00.csv"
        )
        trade_opened_at = datetime(2023, 8, 17, 12, 0, 0, tzinfo=tzutc())
        open_price = 32589
        trade = Trade(
            buy_order_id=1,
            target_symbol="BTC",
            trading_symbol="EUR",
            amount=1,
            open_price=open_price,
            opened_at=trade_opened_at,
            closed_price=None,
            closed_at=None,
        )
        ohlcv_data = csv_ohlcv_market_data_source\
            .get_data(market_credential_service=None)
        current_price = csv_ticker_market_data_source\
            .get_data(
                index_datetime=current_datetime, market_credential_service=None
            )

        df = pd.DataFrame(
            ohlcv_data,
            columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        )
        filtered_df = df[df['Date'] <= trade.opened_at]
        close_prices = filtered_df['Close'].tolist()
        self.assertTrue(trade.is_manual_stop_loss_trigger(
            current_price=current_price["bid"],
            prices=close_prices,
            stop_loss_percentage=2
        ))
