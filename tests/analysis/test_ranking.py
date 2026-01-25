import unittest

from investing_algorithm_framework.analysis.ranking import create_weights
from investing_algorithm_framework.domain import BacktestEvaluationFocus


class TestCreateWeights(unittest.TestCase):
    """Tests for the create_weights function."""

    def test_default_returns_balanced_weights(self):
        """Test that no arguments returns BALANCED weights."""
        weights = create_weights()
        expected = BacktestEvaluationFocus.BALANCED.get_weights()
        self.assertEqual(weights, expected)

    def test_none_focus_returns_balanced_weights(self):
        """Test that focus=None returns BALANCED weights."""
        weights = create_weights(focus=None)
        expected = BacktestEvaluationFocus.BALANCED.get_weights()
        self.assertEqual(weights, expected)

    def test_balanced_focus(self):
        """Test BALANCED focus returns correct weights."""
        weights = create_weights(focus=BacktestEvaluationFocus.BALANCED)
        expected = BacktestEvaluationFocus.BALANCED.get_weights()
        self.assertEqual(weights, expected)

    def test_profit_focus(self):
        """Test PROFIT focus returns correct weights."""
        weights = create_weights(focus=BacktestEvaluationFocus.PROFIT)
        expected = BacktestEvaluationFocus.PROFIT.get_weights()
        self.assertEqual(weights, expected)

    def test_frequency_focus(self):
        """Test FREQUENCY focus returns correct weights."""
        weights = create_weights(focus=BacktestEvaluationFocus.FREQUENCY)
        expected = BacktestEvaluationFocus.FREQUENCY.get_weights()
        self.assertEqual(weights, expected)

    def test_risk_adjusted_focus(self):
        """Test RISK_ADJUSTED focus returns correct weights."""
        weights = create_weights(focus=BacktestEvaluationFocus.RISK_ADJUSTED)
        expected = BacktestEvaluationFocus.RISK_ADJUSTED.get_weights()
        self.assertEqual(weights, expected)

    def test_custom_weights_override_defaults(self):
        """Test that custom_weights override default values."""
        custom = {"sharpe_ratio": 10.0, "win_rate": 5.0}
        weights = create_weights(custom_weights=custom)

        self.assertEqual(weights["sharpe_ratio"], 10.0)
        self.assertEqual(weights["win_rate"], 5.0)

    def test_custom_weights_merge_with_focus(self):
        """Test that custom_weights merge with focus weights."""
        custom = {"sharpe_ratio": 99.0}
        weights = create_weights(
            focus=BacktestEvaluationFocus.BALANCED,
            custom_weights=custom
        )

        # Custom value should override
        self.assertEqual(weights["sharpe_ratio"], 99.0)

        # Other balanced weights should still be present
        balanced_weights = BacktestEvaluationFocus.BALANCED.get_weights()
        for key in balanced_weights:
            if key != "sharpe_ratio":
                self.assertEqual(weights[key], balanced_weights[key])

    def test_custom_weights_add_new_metrics(self):
        """Test that custom_weights can add new metrics not in focus."""
        custom = {"new_custom_metric": 7.5}
        weights = create_weights(custom_weights=custom)

        self.assertEqual(weights["new_custom_metric"], 7.5)

    def test_custom_weights_with_profit_focus(self):
        """Test custom_weights combined with PROFIT focus."""
        custom = {"total_net_gain_percentage": 100.0}
        weights = create_weights(
            focus=BacktestEvaluationFocus.PROFIT,
            custom_weights=custom
        )

        self.assertEqual(weights["total_net_gain_percentage"], 100.0)

    def test_returns_dict_type(self):
        """Test that create_weights always returns a dict."""
        result = create_weights()
        self.assertIsInstance(result, dict)

        result = create_weights(focus=BacktestEvaluationFocus.PROFIT)
        self.assertIsInstance(result, dict)

        result = create_weights(custom_weights={"test": 1.0})
        self.assertIsInstance(result, dict)

    def test_weights_are_numeric(self):
        """Test that all weight values are numeric."""
        for focus in BacktestEvaluationFocus:
            weights = create_weights(focus=focus)
            for key, value in weights.items():
                self.assertIsInstance(
                    value, (int, float),
                    f"Weight for {key} should be numeric, got {type(value)}"
                )

    def test_empty_custom_weights(self):
        """Test that empty custom_weights dict doesn't affect result."""
        weights_no_custom = create_weights()
        weights_empty_custom = create_weights(custom_weights={})

        self.assertEqual(weights_no_custom, weights_empty_custom)

    def test_custom_weights_none_is_same_as_no_custom(self):
        """Test that custom_weights=None gives same result as omitting it."""
        weights_default = create_weights()
        weights_none = create_weights(custom_weights=None)

        self.assertEqual(weights_default, weights_none)

    def test_negative_custom_weights_allowed(self):
        """Test that negative custom weights are allowed (for penalties)."""
        custom = {"some_metric": -5.0}
        weights = create_weights(custom_weights=custom)

        self.assertEqual(weights["some_metric"], -5.0)

    def test_zero_custom_weights_allowed(self):
        """Test that zero custom weights are allowed (to ignore metrics)."""
        custom = {"sharpe_ratio": 0.0}
        weights = create_weights(custom_weights=custom)

        self.assertEqual(weights["sharpe_ratio"], 0.0)

    def test_all_focus_types_return_non_empty_weights(self):
        """Test that all focus types return non-empty weight dictionaries."""
        for focus in BacktestEvaluationFocus:
            weights = create_weights(focus=focus)
            self.assertGreater(
                len(weights), 0,
                f"{focus} should return non-empty weights"
            )


if __name__ == "__main__":
    unittest.main()

