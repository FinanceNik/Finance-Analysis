import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
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


def plot_dividends_comparison(year, transaction_type):
    all_months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    width = 0.25  # narrower bars to fit 3 groups

    # Gather data for each year
    vals = []
    labels = []
    for y in range(year - 2, year + 1):
        months, values = monthly_transaction_summary(y, transaction_type)
        val_aligned = [values[months.index(m)] if m in months else 0 for m in all_months]
        vals.append(val_aligned)
        labels.append(str(y))

    x = np.arange(len(all_months))

    fig, ax = plt.subplots(figsize=(12, 6))

    # Plot bars side by side for 3 years
    for i, (val, label) in enumerate(zip(vals, labels)):
        ax.bar(x + (i - 1) * width, val, width, label=label)

    ax.set_xticks(x)
    ax.set_xticklabels(all_months)
    ax.set_xlabel('Month')
    ax.set_ylabel(f'{transaction_type} Amount')
    ax.set_title(f'Monthly {transaction_type}: Last 3 Years Comparison')
    ax.legend()
    ax.grid(axis='y')

    plt.tight_layout()
    plt.show()


#print(ingest_transactions()["transaction"].unique())

#plot_dividends_comparison(year=2025, transaction_type="Dividend")