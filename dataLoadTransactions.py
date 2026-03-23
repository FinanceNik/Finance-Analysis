import os
import glob
import logging
import pandas as pd
from datetime import datetime
from functools import lru_cache
from utils import standardize_columns

logger = logging.getLogger(__name__)

currentYear = int(datetime.today().strftime('%Y'))
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _find_latest_transactions_file() -> str:
    """Find the most recent transactions CSV in the data directory."""
    files = glob.glob("data/transactions-from-*.csv")
    if not files:
        return ""
    return max(files, key=os.path.getmtime)


_transactions_filepath = _find_latest_transactions_file()


def set_transactions_filepath(path: str):
    global _transactions_filepath
    _transactions_filepath = path
    ingest_transactions.cache_clear()


@lru_cache(maxsize=1)
def ingest_transactions() -> pd.DataFrame:
    if not os.path.exists(_transactions_filepath):
        logger.warning("Transactions file not found: %s", _transactions_filepath)
        return pd.DataFrame()

    df = pd.read_csv(_transactions_filepath, sep=";", encoding="latin-1")
    df = standardize_columns(df)

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


def net_contributions_monthly(year: int) -> dict[str, float]:
    """Net contributions per month: buys netted with sells.

    Returns dict of month abbreviation -> net amount (positive = net invested).
    Crypto Deposits are excluded (staking rewards with no cash amount).
    """
    df = ingest_transactions()
    if df.empty:
        return {m: 0 for m in months}

    df = df.loc[df['date'].dt.year == year].copy()
    contrib_types = ["buy", "sell"]
    df = df.loc[df['transaction'].str.lower().isin(contrib_types)]
    df["month"] = df["date"].dt.strftime("%b")
    # net_amount is negative for buys, positive for sells; negate so buying is positive
    grouped = df.groupby("month")["net_amount"].sum()
    return {m: round(-grouped.get(m, 0), 2) for m in months}


def net_contributions_yearly(year: int) -> float:
    """Total net contributions for a year (positive = net invested)."""
    return round(sum(net_contributions_monthly(year).values()), 2)


def totals(transaction_type):
    two_years_ago_total = yearly_transaction_sum(currentYear - 2, transaction_type)
    prev_year_total = yearly_transaction_sum(currentYear - 1, transaction_type)
    current_year_total = yearly_transaction_sum(currentYear, transaction_type)
    return [two_years_ago_total, prev_year_total, current_year_total]


# ── Realized P&L (FIFO matching) ──────────────────────────────────────────


def _compute_realized_pl() -> pd.DataFrame:
    """Match each sell to prior buys using FIFO and compute realized P&L.

    Returns a DataFrame with one row per sell lot:
        date, symbol, sell_qty, sell_price, proceeds, cost_basis, realized_pl
    """
    df = ingest_transactions()
    if df.empty:
        return pd.DataFrame()

    buys = (
        df.loc[df["transaction"] == "Buy", ["date", "symbol", "quantity", "unit_price"]]
        .sort_values("date")
        .copy()
    )
    sells = (
        df.loc[df["transaction"] == "Sell", ["date", "symbol", "quantity", "unit_price", "net_amount"]]
        .sort_values("date")
        .copy()
    )

    if sells.empty:
        return pd.DataFrame()

    # Build per-symbol FIFO queues: list of (remaining_qty, unit_price)
    fifo: dict[str, list[list]] = {}
    for _, row in buys.iterrows():
        sym = row["symbol"]
        fifo.setdefault(sym, []).append([abs(row["quantity"]), abs(row["unit_price"])])

    results = []
    for _, sell in sells.iterrows():
        sym = sell["symbol"]
        sell_qty = abs(sell["quantity"])
        sell_price = abs(sell["unit_price"])
        proceeds = abs(sell["net_amount"])

        remaining = sell_qty
        cost_basis = 0.0
        queue = fifo.get(sym, [])

        while remaining > 1e-9 and queue:
            lot = queue[0]
            take = min(remaining, lot[0])
            cost_basis += take * lot[1]
            lot[0] -= take
            remaining -= take
            if lot[0] < 1e-9:
                queue.pop(0)

        # If we couldn't match all shares, cost_basis is partial
        matched = remaining < 1e-9
        results.append({
            "date": sell["date"],
            "symbol": sym,
            "sell_qty": sell_qty,
            "sell_price": sell_price,
            "proceeds": proceeds,
            "cost_basis": round(cost_basis, 2) if matched else None,
            "realized_pl": round(proceeds - cost_basis, 2) if matched else None,
        })

    return pd.DataFrame(results)


@lru_cache(maxsize=1)
def realized_pl_table() -> pd.DataFrame:
    """Cached realized P&L table (FIFO)."""
    return _compute_realized_pl()


def realized_pl_by_quarter() -> pd.DataFrame:
    """Realized P&L aggregated by quarter."""
    rpl = realized_pl_table()
    if rpl.empty or "realized_pl" not in rpl.columns:
        return pd.DataFrame()
    df = rpl.dropna(subset=["realized_pl"]).copy()
    if df.empty:
        return pd.DataFrame()
    df["quarter"] = df["date"].dt.to_period("Q")
    grouped = df.groupby("quarter")["realized_pl"].sum().round(2).sort_index()
    return grouped.reset_index().rename(columns={"quarter": "period"})


def realized_pl_by_year() -> pd.DataFrame:
    """Realized P&L aggregated by year."""
    rpl = realized_pl_table()
    if rpl.empty or "realized_pl" not in rpl.columns:
        return pd.DataFrame()
    df = rpl.dropna(subset=["realized_pl"]).copy()
    if df.empty:
        return pd.DataFrame()
    df["year"] = df["date"].dt.year
    grouped = df.groupby("year")["realized_pl"].sum().round(2).sort_index()
    return grouped.reset_index()


def realized_pl_kpis() -> dict:
    """Key metrics for realized P&L."""
    rpl = realized_pl_table()
    if rpl.empty or "realized_pl" not in rpl.columns:
        return {
            "total_pl": 0.0,
            "ytd_pl": 0.0,
            "num_trades": 0,
            "avg_pl": 0.0,
        }
    matched = rpl.dropna(subset=["realized_pl"])
    total = matched["realized_pl"].sum()
    ytd = matched.loc[matched["date"].dt.year == currentYear, "realized_pl"].sum()
    n = len(matched)
    avg = total / n if n else 0.0
    return {
        "total_pl": round(total, 2),
        "ytd_pl": round(ytd, 2),
        "num_trades": n,
        "avg_pl": round(avg, 2),
    }
