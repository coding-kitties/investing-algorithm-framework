from enum import Enum


class TradeRiskType(Enum):
    FIXED = "FIXED"
    TRAILING = "TRAILING"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):
            for status in TradeRiskType:

                if value.upper() == status.value:
                    return status

        raise ValueError("Could not convert value to TradeRiskType")

    @staticmethod
    def from_value(value):

        if isinstance(value, TradeRiskType):
            for risk_type in TradeRiskType:

                if value == risk_type:
                    return risk_type

        elif isinstance(value, str):
            return TradeRiskType.from_string(value)

        raise ValueError("Could not convert value to TradeRiskType")

    def equals(self, other):
        return TradeRiskType.from_value(other) == self
