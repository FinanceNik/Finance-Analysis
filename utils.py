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
