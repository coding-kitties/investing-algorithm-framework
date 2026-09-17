"""Pandas batch evaluation for built-in confluence expressions."""
import pandas as pd

from .confluence import (
    AllOf, AnyOf, AtLeast, ConditionExpression, Not, Operator,
)


def _validate_frame(frame):
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(
            "Confluence frame evaluation requires a pandas DataFrame"
        )
    if not frame.columns.is_unique:
        raise ValueError("Confluence frame columns must be unique")


def _constant(frame, value):
    return pd.Series(value, index=frame.index)


def _expression(expression, frame):
    if isinstance(expression, ConditionExpression):
        predicate = expression.condition

        def column(name):
            key = (
                f"{predicate.timeframe}:{name}"
                if predicate.timeframe else name
            )
            return frame[key]

        left = column(predicate.indicator)
        right = (
            column(predicate.reference) if predicate.reference is not None
            else predicate.value
        )
        available = left.notna()
        if predicate.operator is Operator.BETWEEN:
            low, high = right
            if pd.isna(low) or pd.isna(high):
                return _constant(frame, False), _constant(frame, False)
            matched = left.ge(low) & left.le(high)
        else:
            if isinstance(right, pd.Series):
                available = available & right.notna()
            elif not pd.api.types.is_scalar(right):
                raise TypeError("Batch comparisons require scalar constants")
            elif pd.isna(right):
                return _constant(frame, False), _constant(frame, False)
            operator = predicate.operator
            if operator in (Operator.CROSS_ABOVE, Operator.CROSS_BELOW):
                previous_left = left.shift(1)
                previous_right = (
                    right.shift(1) if isinstance(right, pd.Series) else right
                )
                available = available & previous_left.notna()
                if isinstance(previous_right, pd.Series):
                    available = available & previous_right.notna()
                if operator is Operator.CROSS_ABOVE:
                    matched = previous_left.le(previous_right) & left.gt(right)
                else:
                    matched = previous_left.ge(previous_right) & left.lt(right)
            else:
                methods = {
                    Operator.GT: "gt", Operator.GTE: "ge",
                    Operator.LT: "lt", Operator.LTE: "le",
                    Operator.EQ: "eq", Operator.NEQ: "ne",
                }
                matched = getattr(left, methods[operator])(right)
        return matched.fillna(False).astype(bool) & available, available

    if isinstance(expression, Not):
        matched, available = _expression(expression.expression, frame)
        return ~matched & available, available
    if isinstance(expression, (AllOf, AnyOf, AtLeast)):
        available = _constant(frame, True)
        matches = _constant(frame, 0)
        for child in expression.expressions:
            matched, child_available = _expression(child, frame)
            matches += matched.astype(int)
            available &= child_available
        if isinstance(expression, AllOf):
            minimum = len(expression.expressions)
        elif isinstance(expression, AtLeast):
            minimum = expression.minimum
        else:
            minimum = 1
        return matches.ge(minimum) & available, available
    raise TypeError(
        f"Batch evaluation does not support {type(expression).__name__}; "
        "prepare custom conditions as indicator columns"
    )


def evaluate_expression_series(expression, frame):
    """Return nullable booleans: NA means required data is unavailable."""
    _validate_frame(frame)
    matched, available = _expression(expression, frame)
    return matched.astype("boolean").where(available)


def evaluate_card_series(card, frame):
    """Return score, available, and qualified without per-row objects."""
    _validate_frame(frame)
    available = _constant(frame, True)
    score = _constant(frame, 0.0)
    qualified = _constant(frame, True)

    def evaluate(expression):
        nonlocal available
        matched, expression_available = _expression(expression, frame)
        available &= expression_available
        return matched

    def group(group):
        nonlocal score
        subtotal = _constant(frame, 0.0)
        matches = _constant(frame, 0)
        for rule in group.rules:
            matched = evaluate(rule.expression)
            matches += matched.astype(int)
            subtotal += matched.astype(float) * float(rule.points)
        score += subtotal
        passed = matches.ge(group.minimum_matches)
        if group.minimum_score is not None:
            passed &= subtotal.ge(group.minimum_score)
        return passed

    if card.primary.expression is not None:
        qualified &= evaluate(card.primary.expression)
    else:
        qualified &= group(card.primary)
    for secondary in card.secondary:
        qualified &= group(secondary)
    for rule in card.scoring:
        score += evaluate(rule.expression).astype(float) * float(rule.points)
    for requirement in card.requirements:
        qualified &= evaluate(requirement.expression)
    for veto in card.vetoes:
        qualified &= ~evaluate(veto.expression)
    qualified &= score.ge(card.minimum_score) & available
    return pd.DataFrame({
        "score": score.where(available),
        "available": available,
        "qualified": qualified,
    }, index=frame.index)
