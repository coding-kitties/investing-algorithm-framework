from unittest import TestCase

from investing_algorithm_framework import (
    ScoreCard, ScoreCardEntry, Signal, SignalSide,
)
from investing_algorithm_framework.domain.models.score_card import (
    SCORE_CARD_METADATA_KEY, SCORE_CARD_VERSION,
)


class TestScoreCardEntry(TestCase):

    def test_requires_non_empty_name(self):
        with self.assertRaises(ValueError):
            ScoreCardEntry(name="", value=1)

    def test_rejects_non_scalar_value(self):
        with self.assertRaises(ValueError):
            ScoreCardEntry(name="rsi_14", value=[1, 2, 3])

    def test_accepts_json_scalars(self):
        for value in ("oversold", 28, 28.4, True, None):
            entry = ScoreCardEntry(name="rsi_14", value=value)
            self.assertEqual(value, entry.value)

    def test_to_dict_and_from_dict_round_trip(self):
        entry = ScoreCardEntry(
            name="rsi_14", value=28.4, unit="%",
            description="14-period RSI", group="momentum",
        )
        data = entry.to_dict()
        restored = ScoreCardEntry.from_dict(data)
        self.assertEqual(entry, restored)


class TestScoreCard(TestCase):

    def test_to_dict_includes_version(self):
        card = ScoreCard.of(
            ScoreCardEntry("rsi_14", 28.4),
            summary="RSI oversold",
        )
        data = card.to_dict()
        self.assertEqual(SCORE_CARD_VERSION, data["score_card_version"])
        self.assertEqual("RSI oversold", data["summary"])
        self.assertEqual(1, len(data["entries"]))
        self.assertEqual("rsi_14", data["entries"][0]["name"])

    def test_from_dict_round_trip(self):
        card = ScoreCard(
            entries=[
                ScoreCardEntry("rsi_14", 28.4, unit="%"),
                ScoreCardEntry("close", 41500.0, unit="EUR"),
            ],
            summary="RSI oversold and price above the 200d SMA",
        )
        restored = ScoreCard.from_dict(card.to_dict())
        self.assertEqual(card, restored)

    def test_from_dict_defaults_missing_version(self):
        restored = ScoreCard.from_dict({"entries": []})
        self.assertEqual(SCORE_CARD_VERSION, restored.version)


class TestSignalWithScoreCard(TestCase):

    def test_attaches_score_card_under_reserved_metadata_key(self):
        card = ScoreCard.of(ScoreCardEntry("rsi_14", 28.4))
        signal = Signal(
            symbol="BTC", side=SignalSide.OPEN_LONG
        ).with_score_card(card)

        self.assertIn(SCORE_CARD_METADATA_KEY, signal.metadata)
        self.assertEqual(
            card.to_dict(), signal.metadata[SCORE_CARD_METADATA_KEY]
        )

    def test_preserves_existing_metadata(self):
        card = ScoreCard.of(ScoreCardEntry("rsi_14", 28.4))
        signal = Signal(
            symbol="BTC", side=SignalSide.OPEN_LONG,
            metadata={"signal_source": "ema_cross"},
        ).with_score_card(card)

        self.assertEqual("ema_cross", signal.metadata["signal_source"])
        self.assertIn(SCORE_CARD_METADATA_KEY, signal.metadata)
