"""Unit tests for ``StopLossRule``/``TakeProfitRule.mirror_on_exchange``."""

from unittest import TestCase

from investing_algorithm_framework import StopLossRule, TakeProfitRule


class StopLossRuleMirrorOnExchangeTest(TestCase):
    def test_defaults_to_false(self):
        rule = StopLossRule(10, 100, "BTC")
        self.assertFalse(rule.mirror_on_exchange)

    def test_opt_in(self):
        rule = StopLossRule(10, 100, "BTC", mirror_on_exchange=True)
        self.assertTrue(rule.mirror_on_exchange)


class TakeProfitRuleMirrorOnExchangeTest(TestCase):
    def test_defaults_to_false(self):
        rule = TakeProfitRule(10, 100, "BTC")
        self.assertFalse(rule.mirror_on_exchange)

    def test_opt_in(self):
        rule = TakeProfitRule(10, 100, "BTC", mirror_on_exchange=True)
        self.assertTrue(rule.mirror_on_exchange)
