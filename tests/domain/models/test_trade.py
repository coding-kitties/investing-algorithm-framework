import os
from datetime import datetime, timedelta
from unittest import TestCase



from investing_algorithm_framework import Order
from investing_algorithm_framework.domain import Trade


class Test(TestCase):

    def test_trade(self):
        order = Order(
            external_id="123",
            target_symbol="BTC",
            trading_symbol="EUR",
            order_side="BUY",
            order_type="LIMIT",
            price=10000,
            amount=1,
            filled=1,
            remaining=0,
            status="OPEN",
            created_at=datetime(2017, 8, 17, 12, 42, 48),
        )

        trade_opened_at = datetime(2023, 11, 29)
        trade = Trade(
            id=1,
            orders=[order],
            target_symbol="BTC",
            trading_symbol="EUR",
            amount=1,
            remaining=1,
            open_price=10000,
            opened_at=trade_opened_at,
            closed_at=None,
            status="OPEN",
            cost=10000,
        )
        self.assertEqual(trade.target_symbol, "BTC")
        self.assertEqual(trade.trading_symbol, "EUR")
        self.assertEqual(trade.amount, 1)
        self.assertEqual(trade.open_price, 10000)

    # def test_stop_loss_manual_with_dataframe(self):
    #     """
    #     Test for checking if stoplos function works on trade. The test uses
    #     an ohlcv dataset of BTC/EUR with a 15m timeframe. The start date
    #     of the dataset is 2023-08-07 08:00:00+00:00 and the end
    #     date of the dataset is 2023-12-02 00:00:00+00:00. The trade is
    #     opened at 2023-08-17 12:00:00 with a price of 32589.
    #     """
    #     current_datetime = datetime(2023, 8, 26, 00, 00, 0, tzinfo=tzutc())
    #     resource_dir = os.path.abspath(
    #         os.path.join(
    #             os.path.join(
    #                 os.path.join(
    #                     os.path.join(
    #                         os.path.realpath(__file__),
    #                         os.pardir
    #                     ),
    #                     os.pardir
    #                 ),
    #                 os.pardir
    #             ),
    #             "resources"
    #         )
    #     )
    #     csv_ohlcv_market_data_source = CSVOHLCVMarketDataSource(
    #         identifier="BTC",
    #         market="BITVAVO",
    #         symbol="BTC/EUR",
    #         time_frame="15m",
    #         csv_file_path=f"{resource_dir}/"
    #                       "market_data_sources_for_testing/"
    #                       "OHLCV_BTC-EUR_BINANCE_2h_2023-08-07:07"
    #                       ":59_2023-12-02:00:00.csv"
    #     )
    #     csv_ticker_market_data_source = CSVTickerMarketDataSource(
    #         identifier="BTC",
    #         market="BITVAVO",
    #         symbol="BTC/EUR",
    #         csv_file_path=f"{resource_dir}"
    #                       "/market_data_sources_for_testing/"
    #                       "TICKER_BTC-EUR_BINANCE_2023-08"
    #                       "-23:22:00_2023-12-02:00:00.csv"
    #     )
    #     trade_opened_at = datetime(2023, 8, 24, 22, 0, 0, tzinfo=tzutc())
    #     open_price = 24167.14
    #     trade = Trade(
    #         buy_order_id=1,
    #         target_symbol="BTC",
    #         trading_symbol="EUR",
    #         amount=1,
    #         open_price=open_price,
    #         opened_at=trade_opened_at,
    #         closed_price=None,
    #         closed_at=None,
    #     )
    #     end_date = trade_opened_at + timedelta(days=2)
    #     ohlcv_data = csv_ohlcv_market_data_source \
    #         .get_data(
    #             market_credential_service=None,
    #             start_date=trade_opened_at,
    #             end_date=end_date
    #         )
    #     current_price = csv_ticker_market_data_source \
    #         .get_data(
    #             start_date=end_date, market_credential_service=None
    #         )
    #     self.assertFalse(
    #         trade.is_manual_stop_loss_trigger(
    #             current_price=current_price["bid"],
    #             ohlcv_df=ohlcv_data,
    #             stop_loss_percentage=2
    #         )
    #     )

    #     current_datetime = datetime(2023, 11, 21, tzinfo=tzutc())
    #     ohlcv_data = csv_ohlcv_market_data_source \
    #         .get_data(
    #             market_credential_service=None,
    #             from_time_stamp=trade_opened_at,
    #             to_time_stamp=current_datetime
    #         )
    #     current_price = csv_ticker_market_data_source \
    #         .get_data(
    #             index_datetime=current_datetime, market_credential_service=None
    #         )
    #     open_price = 35679.63
    #     trade = Trade(
    #         buy_order_id=1,
    #         target_symbol="BTC",
    #         trading_symbol="EUR",
    #         amount=1,
    #         open_price=open_price,
    #         opened_at=trade_opened_at,
    #         closed_price=None,
    #         closed_at=None,
    #     )
    #     self.assertFalse(
    #         trade.is_manual_stop_loss_trigger(
    #             current_price=current_price["bid"],
    #             ohlcv_df=ohlcv_data,
    #             stop_loss_percentage=10
    #         )
    #     )
    #     self.assertTrue(
    #         trade.is_manual_stop_loss_trigger(
    #             current_price=current_price["bid"],
    #             ohlcv_df=ohlcv_data,
    #             stop_loss_percentage=2
    #         )
    #     )

    # def test_stop_loss_manual_trade(self):
    #     trade = Trade(
    #         buy_order_id=1,
    #         target_symbol='BTC',
    #         trading_symbol='USDT',
    #         amount=10,
    #         open_price=100,
    #         opened_at=datetime(2021, 1, 1),
    #     )
    #     self.assertTrue(trade.is_manual_stop_loss_trigger(
    #         current_price=101, prices=[100, 110, 80], stop_loss_percentage=2
    #     ))
    #     self.assertFalse(trade.is_manual_stop_loss_trigger(
    #         current_price=101, prices=[100, 110, 80], stop_loss_percentage=20
    #     ))

    #     # Test if the stop loss is triggered when the price
    #     # is lower than the open price
    #     self.assertTrue(
    #         trade.is_manual_stop_loss_trigger(
    #             current_price=80,
    #             prices=[100, 110, 80],
    #             stop_loss_percentage=2
    #         )
    #     )
    #     self.assertFalse(
    #         trade.is_manual_stop_loss_trigger(
    #             current_price=99,
    #             prices=[100, 110, 80],
    #             stop_loss_percentage=2
    #         )
    #     )
    #     self.assertFalse(
    #         trade.is_manual_stop_loss_trigger(
    #             current_price=90,
    #             prices=[100, 110, 80],
    #             stop_loss_percentage=20
    #         )
    #     )
    #     self.assertTrue(
    #         trade.is_manual_stop_loss_trigger(
    #             current_price=80,
    #             prices=[100, 110, 80],
    #             stop_loss_percentage=20
    #         )
    #     )
