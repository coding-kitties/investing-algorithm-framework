"""Symbol-isolated orchestration of the shared native indicator engine."""
from collections.abc import Mapping
from dataclasses import replace

from investing_algorithm_framework.domain import ConfluenceScoreCard, DataType, SignalSide
from investing_algorithm_framework.domain.indicators import (
    ConfluenceScoreConfig, IndicatorConfig,
)
from .indicator_engine import IndicatorEngine


class ConfluenceIndicatorEngine:
    """Bind strategy declarations per target symbol without sharing history."""

    def __init__(self, configs, cards, data_sources, symbols=()):
        if isinstance(configs, Mapping):
            if any(not isinstance(config, IndicatorConfig) or key != config.id
                   for key, config in configs.items()):
                raise ValueError("Config mapping keys must equal config.id")
            configs = configs.values()
        configs = list(configs)
        if not configs or not all(
            isinstance(config, IndicatorConfig) for config in configs
        ):
            raise ValueError(
                "ConfluenceScoringStrategy requires IndicatorConfig "
                "declarations"
            )
        self.configs = {config.id: config for config in configs}
        if len(self.configs) != len(configs):
            raise ValueError("Duplicate indicator id")
        if isinstance(cards, Mapping):
            self.cards = dict(cards)
        else:
            cards = list(cards)
            if not all(
                isinstance(card, ConfluenceScoreConfig) and card.id
                for card in cards
            ):
                raise ValueError(
                    "Card list declarations require non-empty ids"
                )
            self.cards = {card.id: card for card in cards}
            if len(self.cards) != len(cards):
                raise ValueError("Duplicate card id")
        if not self.cards or not all(
            isinstance(name, str) and name.strip()
            and isinstance(card, ConfluenceScoreConfig)
            and card.side is not None
            for name, card in self.cards.items()
        ):
            raise ValueError(
                "ConfluenceScoringStrategy requires named cards "
                "with an explicit side"
            )
        sources = list(data_sources)
        self.data_sources = {
            source.get_identifier(): source for source in sources
        }
        if len(self.data_sources) != len(sources):
            raise ValueError("Duplicate data source identifier")
        for config in configs:
            for identifier in config.source_identifiers or ():
                if identifier not in self.data_sources:
                    raise ValueError(f"Unknown data source: {identifier}")
        pairs = {}
        for source in sources:
            if DataType.OHLCV.equals(source.data_type) and source.symbol:
                target = source.symbol.split("/")[0]
                if target in pairs and pairs[target] != source.symbol:
                    raise ValueError(
                        f"Ambiguous trading pairs for target symbol {target}"
                    )
                pairs[target] = source.symbol
        targets = list(symbols) if symbols else list(pairs)
        if (not targets or any(symbol not in pairs for symbol in targets)
                or len(set(targets)) != len(targets)):
            raise ValueError(
                "Strategy symbols must be unique uppercase "
                "OHLCV target symbols"
            )
        for card in self.cards.values():
            if set(card.symbols) - set(targets):
                raise ValueError(
                    "Card symbols are not configured on the strategy: "
                    f"{card.symbols}"
                )
        self.engines = {}
        self.scale_in_symbols = set()
        self.required_windows = {}
        for symbol in targets:
            bound_configs = []
            for config in configs:
                if (config.symbol is not None
                        and config.symbol.upper()
                        not in (symbol, pairs[symbol])):
                    continue
                if (config.source_identifiers is not None
                        and not any(
                            self.data_sources[identifier].symbol
                            == pairs[symbol]
                            for identifier in config.source_identifiers
                        )):
                    continue
                identifier = config.data_source
                if isinstance(identifier, Mapping):
                    identifier = identifier.get(
                        symbol, identifier.get(pairs[symbol]),
                    )
                    if identifier is None:
                        continue
                if hasattr(identifier, "get_identifier"):
                    identifier = identifier.get_identifier()
                if identifier is not None:
                    if identifier not in self.data_sources:
                        raise ValueError(f"Unknown data source: {identifier}")
                    if self.data_sources[identifier].symbol != pairs[symbol]:
                        continue
                bound_configs.append(replace(
                    config, symbol=pairs[symbol], data_source=identifier,
                ))
            bound_cards = {
                name: card for name, card in self.cards.items()
                if not card.symbols or symbol in card.symbols
            }
            if not bound_cards:
                continue
            bindings = set()
            stages = []
            for card in bound_cards.values():
                binding = card.side, card.scale_in_stage
                if binding in bindings:
                    raise ValueError(
                        f"Duplicate card action for {symbol}: {binding}"
                    )
                bindings.add(binding)
                if card.side is SignalSide.SCALE_IN:
                    if card.scale_in_stage is None:
                        raise ValueError(
                            "SCALE_IN cards require an explicit scale_in_stage"
                        )
                    stages.append(card.scale_in_stage)
            if sorted(stages) != list(range(len(stages))):
                raise ValueError(
                    f"Scale-in stages for {symbol} must be contiguous "
                    "from zero"
                )
            engine = IndicatorEngine(bound_configs, bound_cards, sources)
            self.engines[symbol] = engine
            if stages:
                self.scale_in_symbols.add(symbol)
            for identifier, required in engine.required_windows.items():
                self.required_windows[identifier] = max(
                    required, self.required_windows.get(identifier, 0),
                )
        self.entry_ids = {}
        self.entry_counts = {}
        self.entry_watermarks = {}
        self.position_anchors = {}

    def get_confluence_score_cards(self, *, merge_symbols: bool = True) -> list[ConfluenceScoreCard]:
        """Inspect bound cards, optionally merging identical symbol definitions."""
        if not isinstance(merge_symbols, bool):
            raise TypeError("merge_symbols must be a boolean")
        cards = [
            card
            for symbol, engine in self.engines.items()
            for card in engine.get_confluence_score_cards(symbol)
        ]
        if not merge_symbols:
            return cards
        groups: list[tuple[tuple, list[ConfluenceScoreCard]]] = []
        for card in cards:
            definition = card._inspection_definition()
            for existing, members in groups:
                if definition == existing:
                    members.append(card)
                    break
            else:
                groups.append((definition, [card]))
        return [
            members[0] if len(members) == 1 else replace(
                members[0], symbol=None, configuration=None,
                indicator_configs=None, data_sources=None, symbol_cards=tuple(members),
            )
            for _, members in groups
        ]

    def prepare(self, data):
        self.entry_ids.clear()
        self.entry_counts.clear()
        self.entry_watermarks.clear()
        self.position_anchors.clear()
        for engine in self.engines.values():
            engine.prepare(data)
        return self

    def evaluate(self, data, as_of, *, inactive_cards=None, position_opened_at=None):
        if inactive_cards is not None and set(inactive_cards) - self.engines.keys():
            raise ValueError("Inactive cards reference unknown symbols")
        if position_opened_at is not None and set(position_opened_at) - self.engines.keys():
            raise ValueError("Position entry times reference unknown symbols")
        return {
            symbol: engine.evaluate(
                data, as_of,
                inactive_cards=(inactive_cards or {}).get(symbol),
                position_opened_at=(position_opened_at or {}).get(symbol),
            )
            for symbol, engine in self.engines.items()
        }

    def snapshot(self, evaluations):
        """Flatten symbol evaluations without repeating card values."""
        return [
            record
            for symbol, evaluation in evaluations.items()
            for record in self.engines[symbol].snapshot(evaluation)
        ]

    def confluence_snapshot(self, evaluations):
        return [
            {**record, "symbol": symbol}
            for symbol, evaluation in evaluations.items()
            for record in self.engines[symbol].confluence_snapshot(evaluation)
        ]
