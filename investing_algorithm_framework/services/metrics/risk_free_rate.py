import logging

# Default US 10-year Treasury yield approximation (2%)
DEFAULT_RISK_FREE_RATE = 0.02

logger = logging.getLogger("investing_algorithm_framework")


def get_risk_free_rate_us():
    """
    Retrieves the US 10-year Treasury yield from Yahoo Finance.
    Falls back to a default rate of 4% if yfinance is not installed
    or data is unavailable.

    Returns:
        float: The latest yield as a decimal (e.g., 0.0423 for 4.23%),
        or 0.04 as default fallback.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.info(
            "yfinance not installed, using default risk-free rate "
            f"of {DEFAULT_RISK_FREE_RATE:.0%}. Install yfinance for "
            "live rates: pip install investing-algorithm-framework[yahoo]"
        )
        return DEFAULT_RISK_FREE_RATE

    try:
        ten_year = yf.Ticker("^TNX")
        hist = ten_year.history(period="5d")

        if hist.empty or "Close" not in hist.columns:
            logger.warning(
                "Risk-free rate data is unavailable, "
                f"using default of {DEFAULT_RISK_FREE_RATE:.0%}."
            )
            return DEFAULT_RISK_FREE_RATE

        latest_yield = hist["Close"].dropna().iloc[-1] / 100
        return latest_yield

    except Exception as e:
        logger.warning(
            f"Could not retrieve risk-free rate: {e}. "
            f"Using default of {DEFAULT_RISK_FREE_RATE:.0%}."
        )
        return DEFAULT_RISK_FREE_RATE
        return None
