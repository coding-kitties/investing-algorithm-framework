"""Reconstruct frozen dataclasses with read-only mappings in process workers."""

from collections.abc import Mapping
from dataclasses import fields


def _plain_mappings(value):
    if isinstance(value, Mapping):
        return {key: _plain_mappings(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain_mappings(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_plain_mappings(item) for item in value)
    return value


def _restore_dataclass(cls, state):
    return cls(**state)


def reduce_immutable_dataclass(instance):
    state = {
        field.name: _plain_mappings(getattr(instance, field.name))
        for field in fields(instance) if field.init
    }
    return _restore_dataclass, (type(instance), state)
