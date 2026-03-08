import os
import logging
import pandas as pd
from datetime import datetime
from functools import lru_cache

logger = logging.getLogger(__name__)

currentYear = int(datetime.today().strftime('%Y'))
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# Default filepath — can be overridden via upload
_positions_filepath = "data/Positions_1640083_09012026_10_54.csv"
_transactions_filepath = "data/transactions-from-01012023-to-22112025.csv"


def set_positions_filepath(path: str):
    global _positions_filepath
    _positions_filepath = path
    fetch_data.cache_clear()


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
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


@lru_cache(maxsize=1)
def fetch_data() -> pd.DataFrame:
    if not os.path.exists(_positions_filepath):
        logger.warning("Positions file not found: %s", _positions_filepath)
        return pd.DataFrame()

    df = pd.read_csv(_positions_filepath, sep=",")
    df = _standardize_columns(df)

    for col in df.columns:
        if "date" in col:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    df = df.apply(lambda s: s.str.strip() if s.dtype == "object" else s)
    return df


def get_asset_mapping() -> pd.DataFrame:
    if not os.path.exists(_transactions_filepath):
        logger.warning("Transactions file not found: %s", _transactions_filepath)
        return pd.DataFrame()

    df = pd.read_csv(_transactions_filepath, sep=";")
    df = _standardize_columns(df)
    asset_df = df[['symbol', 'name', 'isin', 'currency']].dropna(subset=['symbol']).drop_duplicates()
    asset_df = asset_df.reset_index(drop=True)
    return asset_df


def portfolio_total_value() -> float:
    df = fetch_data()
    if df.empty:
        return 0
    return int(df["total_value"].sum())


def portfolio_cost_basis() -> float:
    df = fetch_data()
    if df.empty:
        return 0
    return int((df["quantity"] * df["unit_cost"]).sum())


def portfolio_unrealized_pnl() -> float:
    mv = portfolio_total_value()
    cost = portfolio_cost_basis()
    return int(mv - cost)


def portfolio_return_pct() -> float:
    cost = portfolio_cost_basis()
    if cost == 0:
        return 0.0
    return round(portfolio_unrealized_pnl() / cost, 2)


def add_position_pnl_columns() -> pd.DataFrame:
    df = fetch_data()
    if df.empty:
        return df
    df = df.copy()
    df["market_value"] = df["quantity"] * df["price"]
    df["cost_basis"] = df["quantity"] * df["unit_cost"]
    df["unrealized_pnl"] = df["market_value"] - df["cost_basis"]
    df["pnl_pct"] = df["unrealized_pnl"] / df["cost_basis"].replace(0, float("nan"))
    return df


def allocation_by_asset_type() -> pd.DataFrame:
    df = fetch_data()
    if df.empty:
        return pd.DataFrame(columns=["asset_type", "weight"])
    total = portfolio_total_value()
    alloc = df.groupby("asset_type")["total_value"].sum().reset_index()
    alloc["weight"] = alloc["total_value"] / total
    return alloc


def allocation_by_geography() -> pd.DataFrame:
    df = fetch_data()
    if df.empty:
        return pd.DataFrame(columns=["geography", "weight"])
    total = portfolio_total_value()
    alloc = df.groupby("geography")["total_value"].sum().reset_index()
    alloc["weight"] = alloc["total_value"] / total
    return alloc


def allocation_by_currency() -> pd.DataFrame:
    df = fetch_data()
    if df.empty:
        return pd.DataFrame(columns=["currency", "weight"])
    total = portfolio_total_value()
    alloc = df.groupby("currency")["total_value"].sum().reset_index()
    alloc["weight"] = alloc["total_value"] / total
    return alloc


def top_positions(n: int = 5) -> pd.DataFrame:
    df = fetch_data()
    if df.empty:
        return df
    return df.nlargest(n, "total_value")
