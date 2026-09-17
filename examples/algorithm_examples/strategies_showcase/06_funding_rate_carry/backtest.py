"""Funding-rate carry — scaffold only. See README.md."""


def main() -> None:
    raise NotImplementedError(
        "Funding-rate carry is not directly implementable today. "
        "The framework lacks a native funding-rate data provider and a "
        "perp/margin portfolio model. See README.md for the workaround "
        "(custom DataProvider + manual cash-flow booking)."
    )


if __name__ == "__main__":
    main()
