from enum import Enum


class PositionMode(str, Enum):
    NETTING = "netting"
    HEDGE = "hedge"
