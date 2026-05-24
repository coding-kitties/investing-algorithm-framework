import unittest

from investing_algorithm_framework import (
    SlippageModel,
    NoSlippage,
    PercentageSlippage,
    FixedSlippage,
    VolumeImpactSlippage,
    VolumeShareSlippage,
    FixedBasisPointsSlippage,
    TradingCost,
)


class TestNoSlippage(unittest.TestCase):

    def test_buy_no_change(self):
        model = NoSlippage()
        self.assertEqual(model.calculate_slippage(100, "BUY"), 100)

    def test_sell_no_change(self):
        model = NoSlippage()
        self.assertEqual(model.calculate_slippage(100, "SELL"), 100)

    def test_max_fill_amount_returns_full(self):
        model = NoSlippage()
        self.assertEqual(model.max_fill_amount(50), 50)


class TestPercentageSlippage(unittest.TestCase):

    def setUp(self):
        self.model = PercentageSlippage(percentage=0.001)

    def test_buy_increases_price(self):
        # 0.1% slippage on buy
        price = self.model.calculate_slippage(1000, "BUY")
        self.assertAlmostEqual(price, 1001.0)

    def test_sell_decreases_price(self):
        price = self.model.calculate_slippage(1000, "SELL")
        self.assertAlmostEqual(price, 999.0)

    def test_custom_percentage(self):
        model = PercentageSlippage(percentage=0.01)  # 1%
        self.assertAlmostEqual(
            model.calculate_slippage(200, "BUY"), 202.0
        )
        self.assertAlmostEqual(
            model.calculate_slippage(200, "SELL"), 198.0
        )

    def test_max_fill_amount_returns_full(self):
        self.assertEqual(self.model.max_fill_amount(100), 100)


class TestFixedSlippage(unittest.TestCase):

    def test_buy_adds_amount(self):
        model = FixedSlippage(amount=0.50)
        self.assertAlmostEqual(
            model.calculate_slippage(100, "BUY"), 100.50
        )

    def test_sell_subtracts_amount(self):
        model = FixedSlippage(amount=0.50)
        self.assertAlmostEqual(
            model.calculate_slippage(100, "SELL"), 99.50
        )

    def test_max_fill_amount_returns_full(self):
        model = FixedSlippage(amount=0.50)
        self.assertEqual(model.max_fill_amount(100), 100)


class TestVolumeImpactSlippage(unittest.TestCase):

    def setUp(self):
        self.model = VolumeImpactSlippage(
            base_percentage=0.001, impact_power=0.5
        )

    def test_buy_increases_price(self):
        price = self.model.calculate_slippage(
            1000, "BUY", amount=100, volume=10000
        )
        # participation = 100/10000 = 0.01
        # impact = 0.001 * 0.01^0.5 = 0.001 * 0.1 = 0.0001
        expected = 1000 * (1 + 0.001 * (0.01 ** 0.5))
        self.assertAlmostEqual(price, expected, places=6)
        self.assertGreater(price, 1000)

    def test_sell_decreases_price(self):
        price = self.model.calculate_slippage(
            1000, "SELL", amount=100, volume=10000
        )
        expected = 1000 * (1 - 0.001 * (0.01 ** 0.5))
        self.assertAlmostEqual(price, expected, places=6)
        self.assertLess(price, 1000)

    def test_larger_order_more_impact(self):
        small = self.model.calculate_slippage(
            1000, "BUY", amount=10, volume=10000
        )
        large = self.model.calculate_slippage(
            1000, "BUY", amount=1000, volume=10000
        )
        self.assertGreater(large, small)

    def test_no_volume_falls_back_to_base(self):
        price = self.model.calculate_slippage(1000, "BUY")
        # Falls back to base_percentage = 0.001
        self.assertAlmostEqual(price, 1000 * 1.001)

    def test_zero_volume_falls_back_to_base(self):
        price = self.model.calculate_slippage(
            1000, "SELL", amount=10, volume=0
        )
        self.assertAlmostEqual(price, 1000 * (1 - 0.001))

    def test_max_fill_amount_returns_full(self):
        self.assertEqual(self.model.max_fill_amount(100), 100)


class TestVolumeShareSlippage(unittest.TestCase):

    def setUp(self):
        self.model = VolumeShareSlippage(
            volume_limit=0.025, price_impact=0.1
        )

    def test_buy_increases_price(self):
        price = self.model.calculate_slippage(
            100, "BUY", amount=100, volume=10000
        )
        # participation = 100/10000 = 0.01
        # impact = 0.1 * 0.01^2 = 0.00001
        expected = 100 * (1 + 0.1 * (0.01 ** 2))
        self.assertAlmostEqual(price, expected, places=6)
        self.assertGreater(price, 100)

    def test_sell_decreases_price(self):
        price = self.model.calculate_slippage(
            100, "SELL", amount=100, volume=10000
        )
        expected = 100 * (1 - 0.1 * (0.01 ** 2))
        self.assertAlmostEqual(price, expected, places=6)
        self.assertLess(price, 100)

    def test_large_participation_larger_impact(self):
        small = self.model.calculate_slippage(
            100, "BUY", amount=10, volume=10000
        )
        large = self.model.calculate_slippage(
            100, "BUY", amount=500, volume=10000
        )
        self.assertGreater(large, small)

    def test_no_volume_zero_impact(self):
        price = self.model.calculate_slippage(100, "BUY", amount=10)
        self.assertEqual(price, 100)

    def test_zero_volume_zero_impact(self):
        price = self.model.calculate_slippage(
            100, "BUY", amount=10, volume=0
        )
        self.assertEqual(price, 100)

    def test_max_fill_amount_limits_to_volume(self):
        # 2.5% of 10000 = 250
        result = self.model.max_fill_amount(500, volume=10000)
        self.assertEqual(result, 250)

    def test_max_fill_amount_returns_order_when_small(self):
        # 2.5% of 10000 = 250, order is only 100
        result = self.model.max_fill_amount(100, volume=10000)
        self.assertEqual(result, 100)

    def test_max_fill_amount_no_volume(self):
        result = self.model.max_fill_amount(500)
        self.assertEqual(result, 500)


class TestFixedBasisPointsSlippage(unittest.TestCase):

    def setUp(self):
        self.model = FixedBasisPointsSlippage(basis_points=10)

    def test_buy_increases_price(self):
        # 10 bps = 0.1%
        price = self.model.calculate_slippage(1000, "BUY")
        self.assertAlmostEqual(price, 1001.0)

    def test_sell_decreases_price(self):
        price = self.model.calculate_slippage(1000, "SELL")
        self.assertAlmostEqual(price, 999.0)

    def test_one_basis_point(self):
        model = FixedBasisPointsSlippage(basis_points=1)
        price = model.calculate_slippage(10000, "BUY")
        self.assertAlmostEqual(price, 10001.0)

    def test_max_fill_amount_returns_full(self):
        self.assertEqual(self.model.max_fill_amount(100), 100)


class TestTradingCostWithSlippageModel(unittest.TestCase):

    def test_slippage_model_overrides_percentage_buy(self):
        tc = TradingCost(
            slippage_percentage=1.0,
            slippage_model=FixedBasisPointsSlippage(basis_points=10),
        )
        # Should use model (10 bps = 0.1%) not percentage (1%)
        price = tc.get_buy_fill_price(1000)
        self.assertAlmostEqual(price, 1001.0)

    def test_slippage_model_overrides_percentage_sell(self):
        tc = TradingCost(
            slippage_percentage=1.0,
            slippage_model=FixedBasisPointsSlippage(basis_points=10),
        )
        price = tc.get_sell_fill_price(1000)
        self.assertAlmostEqual(price, 999.0)

    def test_volume_share_with_trading_cost(self):
        tc = TradingCost(
            symbol="BTC",
            fee_percentage=0.1,
            slippage_model=VolumeShareSlippage(
                volume_limit=0.025, price_impact=0.1
            ),
        )
        price = tc.get_buy_fill_price(
            50000, amount=100, volume=10000
        )
        self.assertGreater(price, 50000)

    def test_fixed_slippage_with_trading_cost(self):
        tc = TradingCost(
            symbol="ETH",
            fee_percentage=0.1,
            slippage_model=FixedSlippage(amount=0.50),
        )
        price = tc.get_buy_fill_price(3000)
        self.assertAlmostEqual(price, 3000.50)

    def test_get_max_fill_amount_with_model(self):
        tc = TradingCost(
            slippage_model=VolumeShareSlippage(
                volume_limit=0.025, price_impact=0.1
            ),
        )
        # 2.5% of 10000 = 250
        result = tc.get_max_fill_amount(500, volume=10000)
        self.assertEqual(result, 250)

    def test_get_max_fill_amount_without_model(self):
        tc = TradingCost(slippage_percentage=1.0)
        result = tc.get_max_fill_amount(500, volume=10000)
        self.assertEqual(result, 500)

    def test_backward_compat_no_model(self):
        tc = TradingCost(slippage_percentage=1.0)
        self.assertAlmostEqual(tc.get_buy_fill_price(100), 101.0)
        self.assertAlmostEqual(tc.get_sell_fill_price(100), 99.0)

    def test_backward_compat_no_slippage(self):
        tc = TradingCost()
        self.assertAlmostEqual(tc.get_buy_fill_price(100), 100.0)
        self.assertAlmostEqual(tc.get_sell_fill_price(100), 100.0)


class TestCustomSlippageModel(unittest.TestCase):

    def test_custom_model_works(self):
        class MySlippage(SlippageModel):
            def calculate_slippage(
                self, price, order_side, amount=None, volume=None
            ):
                if order_side == "BUY":
                    return price * 1.05
                return price * 0.95

        tc = TradingCost(slippage_model=MySlippage())
        self.assertAlmostEqual(tc.get_buy_fill_price(100), 105.0)
        self.assertAlmostEqual(tc.get_sell_fill_price(100), 95.0)


if __name__ == "__main__":
    unittest.main()
