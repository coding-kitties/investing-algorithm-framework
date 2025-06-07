import yfinance as yf


def get_risk_free_rate_us():
    ten_year = yf.Ticker("^TNX")
    hist = ten_year.history(period="5d")
    latest_yield = hist["Close"].iloc[-1] / 100
    return latest_yield
