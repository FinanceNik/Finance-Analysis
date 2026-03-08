import os
import logging
import pandas as pd
from datetime import datetime
from functools import lru_cache

logger = logging.getLogger(__name__)

currentYear = int(datetime.today().strftime('%Y'))
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

_transactions_filepath = "data/transactions-from-30122022-to-09012026.csv"


def set_transactions_filepath(path: str):
    global _transactions_filepath
    _transactions_filepath = path
    ingest_transactions.cache_clear()


@lru_cache(maxsize=1)
def ingest_transactions() -> pd.DataFrame:
    if not os.path.exists(_transactions_filepath):
        logger.warning("Transactions file not found: %s", _transactions_filepath)
        return pd.DataFrame()

    df = pd.read_csv(_transactions_filepath, sep=";")
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
        .str.replace("#", "number")
        .str.replace("__", "_")
    )

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True)

    def to_numeric(series: pd.Series) -> pd.Series:
        if series.dtype == object:
            cleaned = (
                series
                .str.replace(" ", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
            return pd.to_numeric(cleaned, errors="coerce")
        return pd.to_numeric(series)

    numeric_candidates = [
        col for col in df.columns
        if any(key in col for key in ["amount", "quantity", "price", "balance", "value"])
    ]

    for col in numeric_candidates:
        df[col] = to_numeric(df[col])

    return df


def yearly_transaction_summary():
    df = ingest_transactions()
    if df.empty:
        return [], []
    df = df.loc[df["transaction"] == "Dividend"]

    df = df.copy()
    df["year"] = df["date"].dt.year
    grouped = (
        df.groupby("year")["net_amount"]
        .sum()
        .round(2)
        .sort_index()
    )

    year_labels = [str(year) for year in grouped.index]
    values = list(grouped.values)
    return year_labels, values


def monthly_transaction_summary(
    year: int,
    transaction_type: str | list[str]
) -> tuple[list[str], list[float]]:
    if isinstance(transaction_type, str):
        transaction_types = [transaction_type.lower()]
    else:
        transaction_types = [t.lower() for t in transaction_type]

    df = ingest_transactions()
    if df.empty:
        return [], []

    df = df.loc[df['date'].dt.year == year]
    df = df.loc[df['transaction'].str.lower().isin(transaction_types)]

    df = df.copy()
    df["month"] = df["date"].dt.strftime("%b")
    grouped = df.groupby("month")["net_amount"].sum().sort_index()

    return list(grouped.index), list(grouped.values)


def total_transaction_amount(year: int, transaction_type: str | list[str]) -> float:
    df = ingest_transactions()
    if df.empty:
        return 0.0
    if isinstance(transaction_type, str):
        transaction_types = [transaction_type.lower()]
    else:
        transaction_types = [t.lower() for t in transaction_type]

    filtered = df.loc[
        (df['date'].dt.year == year) &
        (df['transaction'].str.lower().isin(transaction_types))
    ]
    total = filtered['net_amount'].sum()
    return round(total, 2)


def average_transaction_amount(year: int, transaction_type: str | list[str]) -> float:
    df = ingest_transactions()
    if df.empty:
        return 0.0
    if isinstance(transaction_type, str):
        transaction_types = [transaction_type.lower()]
    else:
        transaction_types = [t.lower() for t in transaction_type]

    filtered = df.loc[
        (df['date'].dt.year == year) &
        (df['transaction'].str.lower().isin(transaction_types))
    ]
    avg = filtered['net_amount'].mean()
    return avg


def count_transactions(year: int, transaction_type: str | list[str]) -> int:
    df = ingest_transactions()
    if df.empty:
        return 0
    if isinstance(transaction_type, str):
        transaction_types = [transaction_type.lower()]
    else:
        transaction_types = [t.lower() for t in transaction_type]

    filtered = df.loc[
        (df['date'].dt.year == year) &
        (df['transaction'].str.lower().isin(transaction_types))
    ]
    return filtered.shape[0]


def yearly_transaction_sum(year, transaction_type) -> float:
    months_list, values = monthly_transaction_summary(year, transaction_type)
    return round(sum(values), 2)


def monthly_totals(transaction_type):
    """Return (months, vals_2y_ago, vals_prev, vals_current)."""
    months_2y, values_2y = monthly_transaction_summary(currentYear - 2, transaction_type)
    months_prev, values_prev = monthly_transaction_summary(currentYear - 1, transaction_type)
    months_current, values_current = monthly_transaction_summary(currentYear, transaction_type)

    dict_2y = dict(zip(months_2y, values_2y))
    dict_prev = dict(zip(months_prev, values_prev))
    dict_current = dict(zip(months_current, values_current))

    vals_2y = [dict_2y.get(m, 0) for m in months]
    vals_prev = [dict_prev.get(m, 0) for m in months]
    vals_current = [dict_current.get(m, 0) for m in months]

    return months, vals_2y, vals_prev, vals_current


def totals(transaction_type):
    two_years_ago_total = yearly_transaction_sum(currentYear - 2, transaction_type)
    prev_year_total = yearly_transaction_sum(currentYear - 1, transaction_type)
    current_year_total = yearly_transaction_sum(currentYear, transaction_type)
    return [two_years_ago_total, prev_year_total, current_year_total]
