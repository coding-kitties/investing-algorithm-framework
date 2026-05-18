"""Unit tests for ``CooldownRule`` and ``CooldownTracker``."""

from unittest import TestCase

from investing_algorithm_framework import (
    CooldownBlocks,
    CooldownRule,
    CooldownTracker,
    CooldownTrigger,
)


class CooldownRuleTest(TestCase):
    def test_defaults(self):
        rule = CooldownRule(bars=3)
        self.assertIsNone(rule.symbol)
        self.assertIs(rule.trigger, CooldownTrigger.ANY)
        self.assertIs(rule.blocks, CooldownBlocks.ANY)
        self.assertEqual(rule.bars, 3)
        self.assertTrue(rule.is_portfolio_scoped)

    def test_string_coercion(self):
        rule = CooldownRule(
            symbol="BTC", trigger="sell", blocks="buy", bars=2
        )
        self.assertIs(rule.trigger, CooldownTrigger.SELL)
        self.assertIs(rule.blocks, CooldownBlocks.BUY)

    def test_negative_bars_raises(self):
        with self.assertRaises(ValueError):
            CooldownRule(bars=-1)

    def test_zero_bars_allowed(self):
        rule = CooldownRule(bars=0)
        self.assertEqual(rule.bars, 0)

    def test_invalid_trigger_raises(self):
        with self.assertRaises(ValueError):
            CooldownRule(trigger="hold", bars=1)

    def test_invalid_blocks_raises(self):
        with self.assertRaises(ValueError):
            CooldownRule(blocks="hodl", bars=1)

    def test_applies_to_symbol(self):
        portfolio = CooldownRule(bars=1)
        scoped = CooldownRule(symbol="BTC", bars=1)
        self.assertTrue(portfolio.applies_to_symbol("BTC"))
        self.assertTrue(portfolio.applies_to_symbol("ETH"))
        self.assertTrue(scoped.applies_to_symbol("BTC"))
        self.assertFalse(scoped.applies_to_symbol("ETH"))

    def test_trigger_matches(self):
        any_rule = CooldownRule(trigger="any", bars=1)
        sell_rule = CooldownRule(trigger="sell", bars=1)
        self.assertTrue(any_rule.trigger_matches("buy"))
        self.assertTrue(any_rule.trigger_matches("sell"))
        self.assertTrue(sell_rule.trigger_matches("sell"))
        self.assertFalse(sell_rule.trigger_matches("buy"))

    def test_blocks_signal(self):
        any_rule = CooldownRule(blocks="any", bars=1)
        buy_rule = CooldownRule(blocks="buy", bars=1)
        self.assertTrue(any_rule.blocks_signal("buy"))
        self.assertTrue(any_rule.blocks_signal("sell"))
        self.assertTrue(buy_rule.blocks_signal("buy"))
        self.assertFalse(buy_rule.blocks_signal("sell"))


class CooldownTrackerTest(TestCase):
    def setUp(self):
        self.tracker = CooldownTracker()

    def test_no_rules_never_blocks(self):
        self.tracker.record(symbol="BTC", order_side="buy", bar_index=0)
        blocked, rule = self.tracker.is_blocked(
            [], signal_side="buy", symbol="BTC", bar_index=1,
        )
        self.assertFalse(blocked)
        self.assertIsNone(rule)

    def test_zero_bars_is_noop(self):
        rules = [CooldownRule(symbol="BTC", bars=0)]
        self.tracker.record(symbol="BTC", order_side="buy", bar_index=0)
        blocked, _ = self.tracker.is_blocked(
            rules, signal_side="buy", symbol="BTC", bar_index=0,
        )
        self.assertFalse(blocked)

    def test_no_event_recorded_not_blocked(self):
        rules = [CooldownRule(symbol="BTC", bars=3)]
        blocked, _ = self.tracker.is_blocked(
            rules, signal_side="buy", symbol="BTC", bar_index=10,
        )
        self.assertFalse(blocked)

    def test_symbol_scoped_blocks_then_releases(self):
        rules = [CooldownRule(symbol="BTC", bars=3)]
        self.tracker.record(symbol="BTC", order_side="buy", bar_index=5)
        # bar 5: 5-5=0 < 3 -> blocked
        blocked, vetoer = self.tracker.is_blocked(
            rules, signal_side="buy", symbol="BTC", bar_index=5,
        )
        self.assertTrue(blocked)
        self.assertIs(vetoer, rules[0])
        # bar 7: 2 < 3 -> blocked
        blocked, _ = self.tracker.is_blocked(
            rules, signal_side="buy", symbol="BTC", bar_index=7,
        )
        self.assertTrue(blocked)
        # bar 8: 3 < 3 -> allowed
        blocked, _ = self.tracker.is_blocked(
            rules, signal_side="buy", symbol="BTC", bar_index=8,
        )
        self.assertFalse(blocked)

    def test_other_symbol_not_blocked(self):
        rules = [CooldownRule(symbol="BTC", bars=3)]
        self.tracker.record(symbol="BTC", order_side="buy", bar_index=0)
        blocked, _ = self.tracker.is_blocked(
            rules, signal_side="buy", symbol="ETH", bar_index=1,
        )
        self.assertFalse(blocked)

    def test_trigger_side_specific(self):
        # Only a sell restarts the cooldown, only buy gets blocked.
        rules = [CooldownRule(
            symbol="BTC", trigger="sell", blocks="buy", bars=4,
        )]
        # A buy at bar 0 must NOT trigger this rule.
        self.tracker.record(symbol="BTC", order_side="buy", bar_index=0)
        blocked, _ = self.tracker.is_blocked(
            rules, signal_side="buy", symbol="BTC", bar_index=1,
        )
        self.assertFalse(blocked)
        # A sell at bar 5 triggers the rule.
        self.tracker.record(symbol="BTC", order_side="sell", bar_index=5)
        blocked, _ = self.tracker.is_blocked(
            rules, signal_side="buy", symbol="BTC", bar_index=6,
        )
        self.assertTrue(blocked)
        # Sells are not blocked by a buy-only rule.
        blocked, _ = self.tracker.is_blocked(
            rules, signal_side="sell", symbol="BTC", bar_index=6,
        )
        self.assertFalse(blocked)

    def test_blocks_any_covers_both_sides(self):
        rules = [CooldownRule(
            symbol="BTC", trigger="sell", blocks="any", bars=2,
        )]
        self.tracker.record(symbol="BTC", order_side="sell", bar_index=0)
        for side in ("buy", "sell"):
            blocked, _ = self.tracker.is_blocked(
                rules, signal_side=side, symbol="BTC", bar_index=1,
            )
            self.assertTrue(blocked)

    def test_portfolio_scoped_blocks_any_symbol(self):
        rules = [CooldownRule(trigger="sell", blocks="buy", bars=3)]
        self.tracker.record(symbol="BTC", order_side="sell", bar_index=10)
        # ETH buy is also blocked because the rule is portfolio-scoped.
        blocked, vetoer = self.tracker.is_blocked(
            rules, signal_side="buy", symbol="ETH", bar_index=11,
        )
        self.assertTrue(blocked)
        self.assertIs(vetoer, rules[0])

    def test_any_trigger_matches_both_sides(self):
        rules = [CooldownRule(symbol="BTC", trigger="any", bars=2)]
        self.tracker.record(symbol="BTC", order_side="buy", bar_index=0)
        blocked, _ = self.tracker.is_blocked(
            rules, signal_side="sell", symbol="BTC", bar_index=1,
        )
        self.assertTrue(blocked)

    def test_multiple_rules_first_match_wins(self):
        short_rule = CooldownRule(symbol="BTC", bars=1)
        long_rule = CooldownRule(symbol="BTC", bars=10)
        rules = [short_rule, long_rule]
        self.tracker.record(symbol="BTC", order_side="buy", bar_index=0)
        # bar 5: short_rule allows (5-0=5, !<1), long_rule blocks (5<10).
        blocked, vetoer = self.tracker.is_blocked(
            rules, signal_side="buy", symbol="BTC", bar_index=5,
        )
        self.assertTrue(blocked)
        self.assertIs(vetoer, long_rule)

    def test_record_advances_event(self):
        rules = [CooldownRule(symbol="BTC", bars=3)]
        self.tracker.record(symbol="BTC", order_side="buy", bar_index=0)
        # New event at bar 10 should reset window.
        self.tracker.record(symbol="BTC", order_side="buy", bar_index=10)
        blocked, _ = self.tracker.is_blocked(
            rules, signal_side="buy", symbol="BTC", bar_index=11,
        )
        self.assertTrue(blocked)

    def test_record_does_not_regress(self):
        rules = [CooldownRule(symbol="BTC", bars=3)]
        self.tracker.record(symbol="BTC", order_side="buy", bar_index=10)
        # An older event must not overwrite the newer one.
        self.tracker.record(symbol="BTC", order_side="buy", bar_index=2)
        blocked, _ = self.tracker.is_blocked(
            rules, signal_side="buy", symbol="BTC", bar_index=12,
        )
        self.assertTrue(blocked)

    def test_reset_clears_events(self):
        rules = [CooldownRule(symbol="BTC", bars=3)]
        self.tracker.record(symbol="BTC", order_side="buy", bar_index=0)
        self.tracker.reset()
        blocked, _ = self.tracker.is_blocked(
            rules, signal_side="buy", symbol="BTC", bar_index=1,
        )
        self.assertFalse(blocked)
