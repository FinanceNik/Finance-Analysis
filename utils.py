import os
import time

import pandas as pd
import config


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize DataFrame column names: strip, lowercase, normalize separators."""
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
        .str.replace("#", "number")
        .str.replace("__", "_")
    )
    return df


def convert_to_base(amount: float, from_currency: str, fx_rates: dict) -> float:
    """Convert an amount from *from_currency* to the base currency.

    Parameters
    ----------
    amount : float
        Value in the source currency.
    from_currency : str
        ISO currency code of the source (e.g. 'USD').
    fx_rates : dict
        Mapping of currency code -> rate in base currency
        (as returned by fetchAPI.fetch_fx_rates).

    Returns
    -------
    float
        The equivalent value in the base currency.
    """
    rate = fx_rates.get(from_currency.upper(), 1.0)
    return amount * rate


def format_currency(value: float, currency: str | None = None) -> str:
    """Format a numeric value with the appropriate currency symbol.

    Parameters
    ----------
    value : float
        The monetary value to format.
    currency : str, optional
        ISO currency code (e.g. 'USD', 'CHF'). Defaults to BASE_CURRENCY.

    Returns
    -------
    str
        Formatted string, e.g. "CHF 273,659" or "$1,234".
    """
    if currency is None:
        currency = config.BASE_CURRENCY
    symbol = config.CURRENCY_SYMBOLS.get(currency.upper(), currency)
    formatted = f"{value:,.0f}"
    # For non-abbreviated symbols (like CHF), use space separator
    if len(symbol) > 1:
        return f"{symbol} {formatted}"
    return f"{symbol}{formatted}"


# ── Symbol mapping ──────────────────────────────────────────────────


def load_symbol_mapping():
    """Load broker symbol -> Yahoo ticker mapping from data/mapping.csv."""
    path = os.path.join("data", "mapping.csv")
    if not os.path.exists(path):
        return {}
    try:
        mapping = pd.read_csv(path)
        mapping = standardize_columns(mapping)
        return dict(zip(mapping["symbol"], mapping["ticker"]))
    except Exception:
        return {}


# ── yfinance cache ──────────────────────────────────────────────────

_yf_cache = {}
_YF_TTL = 300  # 5 minutes


def yf_cached_info(ticker):
    """Fetch yfinance .info with 5-minute cache."""
    now = time.time()
    key = f"info:{ticker}"
    if key in _yf_cache and now - _yf_cache[key][1] < _YF_TTL:
        return _yf_cache[key][0]
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        _yf_cache[key] = (info, now)
        return info
    except Exception:
        return {}


def yf_cached_price(ticker):
    """Fetch current price with 5-minute cache."""
    info = yf_cached_info(ticker)
    return info.get("currentPrice", info.get("regularMarketPrice", None))


def clear_yf_cache():
    """Clear the yfinance cache (called on Refresh)."""
    _yf_cache.clear()
