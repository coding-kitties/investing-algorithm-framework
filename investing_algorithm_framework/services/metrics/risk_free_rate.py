import yfinance as yf
import logging


logger = logging.getLogger("investing_algorithm_framework")


def get_risk_free_rate_us():
    """
    Retrieves the US 10-year Treasury yield from Yahoo Finance.

    Returns:
        float or None: The latest yield as a decimal (e.g., 0.0423 for 4.23%), or None if unavailable.
    """
    try:
        ten_year = yf.Ticker("^TNX")
        hist = ten_year.history(period="5d")

        if hist.empty or "Close" not in hist.columns:
            logger.warning("Risk-free rate data is unavailable or malformed.")
            return None

        latest_yield = hist["Close"].dropna().iloc[-1] / 100
        return latest_yield

    except Exception as e:
        logger.warning(f"Could not retrieve risk-free rate: {e}")
        return None
