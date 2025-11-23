import pandas as pd
from datetime import datetime

currentYear = int(datetime.today().strftime('%Y'))  # the current year
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def ingest_transactions() -> pd.DataFrame:
    df = pd.read_csv("data/transactions-from-01012023-to-22112025.csv", sep=";")
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
        .str.replace("#", "number")
        .str.replace("__", "_")
    )

    # --- Convert date column ---
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True)

    # --- Numeric cleaning helper ---
    def to_numeric(series: pd.Series) -> pd.Series:
        # Remove thousands separators and handle comma decimal formats
        if series.dtype == object:
            cleaned = (
                series
                .str.replace(" ", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
            return pd.to_numeric(cleaned, errors="coerce")
        return pd.to_numeric(series)

    # --- Convert all numeric-like columns ---
    numeric_candidates = [
        col for col in df.columns
        if any(key in col for key in [
            "amount", "quantity", "price", "balance", "value"
        ])
    ]

    for col in numeric_candidates:
        df[col] = to_numeric(df[col])

    return df


def monthly_transaction_summary(
    year: int,
    transaction_type: str | list[str]
) -> tuple[list[str], list[float]]:
    if isinstance(transaction_type, str):
        transaction_types = [transaction_type.lower()]
    else:
        transaction_types = [t.lower() for t in transaction_type]

    df = ingest_transactions()

    df = df.loc[df['date'].dt.year == year]
    df = df.loc[df['transaction'] == transaction_type]


    # Extract 3-character month name and group
    df["month"] = df["date"].dt.strftime("%b")
    grouped = df.groupby("month")["net_amount"].sum().sort_index()

    # Lists for use elsewhere (plotting, reporting)
    months = list(grouped.index)
    values = list(grouped.values)
    return months, values


def total_transaction_amount(year: int, transaction_type: str | list[str]) -> float:
    df = ingest_transactions()
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
    if isinstance(transaction_type, str):
        transaction_types = [transaction_type.lower()]
    else:
        transaction_types = [t.lower() for t in transaction_type]

    filtered = df.loc[
        (df['date'].dt.year == year) &
        (df['transaction'].str.lower().isin(transaction_types))
        ]
    count = filtered.shape[0]
    return count

def yearly_transaction_sum(year, transaction_type) -> float:
    months, values = monthly_transaction_summary(year, transaction_type)
    return round(sum(values), 2)


def monthly_totals(transaction_type):
    months_prev, values_prev = monthly_transaction_summary(currentYear - 1, transaction_type)
    months_current, values_current = monthly_transaction_summary(currentYear, transaction_type)

    dict_prev = dict(zip(months_prev, values_prev))
    dict_current = dict(zip(months_current, values_current))

    vals_prev = [dict_prev.get(m, 0) for m in months]
    vals_current = [dict_current.get(m, 0) for m in months]

    return months, vals_prev, vals_current




def totals(transaction_type):
    current_year_total = yearly_transaction_sum(currentYear, transaction_type)
    prev_year_total = yearly_transaction_sum(currentYear - 1, transaction_type)
    return [prev_year_total, current_year_total]