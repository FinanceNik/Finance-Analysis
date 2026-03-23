import os
import re
import logging
import glob
import pandas as pd
from datetime import datetime
from functools import lru_cache
import config
from utils import standardize_columns, convert_to_base

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


def _extract_account_id(filepath: str) -> str:
    """Extract account ID from a positions filename like Positions_1640083_..."""
    basename = os.path.basename(filepath)
    match = re.search(r"Positions_(\d+)_", basename)
    return match.group(1) if match else "Unknown"


def _find_latest_positions_file() -> str:
    """Find the most recent positions file (CSV or XLS) in the data directory."""
    patterns = ["data/Positions_*.csv", "data/Positions_*.xls", "data/Positions_*.xlsx"]
    all_files = []
    for pattern in patterns:
        all_files.extend(glob.glob(pattern))
    if not all_files:
        return ""
    # Return the most recently modified file
    return max(all_files, key=os.path.getmtime)


def get_all_account_ids() -> list:
    """Get all unique account IDs from position filenames in the data directory."""
    patterns = ["data/Positions_*.csv", "data/Positions_*.xls", "data/Positions_*.xlsx"]
    all_files = []
    for pattern in patterns:
        all_files.extend(glob.glob(pattern))
    ids = set()
    for f in all_files:
        aid = _extract_account_id(f)
        if aid != "Unknown":
            ids.add(aid)
    return sorted(ids)


_positions_filepath = _find_latest_positions_file()


def set_positions_filepath(path: str):
    global _positions_filepath
    _positions_filepath = path
    fetch_data.cache_clear()
    load_historical_data.cache_clear()


@lru_cache(maxsize=1)
def load_historical_data() -> pd.DataFrame:
    path = "data/historical_data.csv"
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path, index_col=0, parse_dates=True)


def _parse_xls_positions(filepath: str) -> pd.DataFrame:
    """Parse the broker XLS export which has category header rows and subtotal rows."""
    df = pd.read_excel(filepath)
    df = standardize_columns(df)

    # The first unnamed column contains category headers like "Shares", "ETFs", "Cryptocurrencies"
    # and subtotal/total rows. We need to extract the category and filter to actual position rows.
    first_col = df.columns[0]  # usually ' ' or unnamed

    # Identify category rows — they have text in the first column and NaN in numeric columns
    current_category = "Unknown"
    categories = []
    keep_rows = []

    for idx, row in df.iterrows():
        first_val = str(row[first_col]).strip() if pd.notna(row[first_col]) else ""
        symbol = str(row.get("symbol", "")).strip() if pd.notna(row.get("symbol")) else ""

        # Category header rows: first column has text, symbol is empty
        if first_val and not symbol:
            # Skip subtotal and total rows
            if "subtotal" in first_val.lower() or first_val.lower() == "total":
                continue
            current_category = first_val
            continue

        # Subtotal/total rows in first column
        if "subtotal" in first_val.lower() or first_val.lower() == "total":
            continue

        # Actual position rows: have a symbol that isn't a subtotal/total
        if symbol and "subtotal" not in symbol.lower() and symbol.lower() != "total":
            categories.append(current_category)
            keep_rows.append(idx)

    if not keep_rows:
        return pd.DataFrame()

    df_positions = df.loc[keep_rows].copy()
    df_positions["asset_type"] = categories

    # Drop the first unnamed column and any fully empty columns
    if first_col in df_positions.columns:
        df_positions = df_positions.drop(columns=[first_col])
    unnamed_cols = [c for c in df_positions.columns if "unnamed" in str(c).lower()]
    df_positions = df_positions.drop(columns=unnamed_cols, errors="ignore")

    # Map symbols to geography: try CSV mapping first, fall back to config.GEO_MAP
    geography_map = _load_geography_map()
    if not geography_map:
        geography_map = config.GEO_MAP
    df_positions["geography"] = df_positions["symbol"].map(geography_map).fillna("Other")

    # Ensure numeric columns are numeric
    for col in ["quantity", "unit_cost", "total_value", "price"]:
        if col in df_positions.columns:
            df_positions[col] = pd.to_numeric(df_positions[col], errors="coerce")

    # Rename ccy to currency for consistency
    if "ccy" in df_positions.columns and "currency" not in df_positions.columns:
        df_positions = df_positions.rename(columns={"ccy": "currency"})

    df_positions = df_positions.reset_index(drop=True)
    return df_positions


def _load_geography_map() -> dict:
    """Load geography mapping from the CSV positions file if it exists."""
    csv_files = glob.glob("data/Positions_*.csv")
    for f in csv_files:
        try:
            df = pd.read_csv(f, sep=",")
            df = standardize_columns(df)
            if "symbol" in df.columns and "geography" in df.columns:
                return dict(zip(df["symbol"].str.strip(), df["geography"].str.strip()))
        except Exception:
            continue
    return {}


@lru_cache(maxsize=1)
def fetch_data() -> pd.DataFrame:
    if not _positions_filepath or not os.path.exists(_positions_filepath):
        logger.warning("Positions file not found: %s", _positions_filepath)
        return pd.DataFrame()

    ext = os.path.splitext(_positions_filepath)[1].lower()

    if ext in (".xls", ".xlsx"):
        df = _parse_xls_positions(_positions_filepath)
    else:
        df = pd.read_csv(_positions_filepath, sep=",")
        df = standardize_columns(df)
        for col in df.columns:
            if "date" in col:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        df = df.apply(lambda s: s.str.strip() if s.dtype == "object" else s)

    # Normalize ccy → currency for consistency
    if "ccy" in df.columns and "currency" not in df.columns:
        df = df.rename(columns={"ccy": "currency"})

    # Add account_id column from filename
    df["account_id"] = _extract_account_id(_positions_filepath)

    # ── FX conversion: add base_value column if currency data is present ──
    if "currency" in df.columns and "total_value" in df.columns:
        try:
            from fetchAPI import fetch_fx_rates
            fx_rates = fetch_fx_rates(base=config.BASE_CURRENCY)
            df["base_value"] = df.apply(
                lambda row: convert_to_base(
                    row["total_value"],
                    str(row["currency"]).strip(),
                    fx_rates,
                ),
                axis=1,
            )
        except Exception as e:
            logger.warning("FX conversion failed, falling back to total_value: %s", e)
            df["base_value"] = df["total_value"]
    else:
        # No currency column — base_value mirrors total_value
        if "total_value" in df.columns:
            df["base_value"] = df["total_value"]

    return df


def get_asset_mapping() -> pd.DataFrame:
    if not os.path.exists(_transactions_filepath):
        logger.warning("Transactions file not found: %s", _transactions_filepath)
        return pd.DataFrame()

    df = pd.read_csv(_transactions_filepath, sep=";", encoding="latin-1")
    df = standardize_columns(df)
    asset_df = df[['symbol', 'name', 'isin', 'currency']].dropna(subset=['symbol']).drop_duplicates()
    asset_df = asset_df.reset_index(drop=True)
    return asset_df


def portfolio_total_value() -> float:
    df = fetch_data()
    if df.empty:
        return 0
    # Prefer base_value (FX-converted) when available
    col = "base_value" if "base_value" in df.columns else "total_value"
    return int(df[col].sum())


def portfolio_cost_basis() -> float:
    df = fetch_data()
    if df.empty:
        return 0
    raw_cost = df["quantity"] * df["unit_cost"]
    # Convert cost basis to base currency when FX data is available
    if "currency" in df.columns:
        try:
            from fetchAPI import fetch_fx_rates
            fx_rates = fetch_fx_rates(base=config.BASE_CURRENCY)
            base_cost = raw_cost.copy()
            for idx in df.index:
                ccy = str(df.loc[idx, "currency"]).strip()
                rate = fx_rates.get(ccy, 1.0)
                base_cost.loc[idx] = raw_cost.loc[idx] * rate
            return int(base_cost.sum())
        except Exception:
            pass
    return int(raw_cost.sum())


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
    if "base_value" in df.columns:
        df["market_value"] = df["base_value"]
    else:
        df["market_value"] = df["quantity"] * df["price"]
    df["cost_basis"] = df["quantity"] * df["unit_cost"]
    df["unrealized_pnl"] = df["market_value"] - df["cost_basis"]
    df["pnl_pct"] = df["unrealized_pnl"] / df["cost_basis"].replace(0, float("nan"))
    return df


def _val_col(df: pd.DataFrame) -> str:
    """Return the best value column: base_value (FX-converted) or total_value."""
    return "base_value" if "base_value" in df.columns else "total_value"


def allocation_by_asset_type() -> pd.DataFrame:
    df = fetch_data()
    if df.empty:
        return pd.DataFrame(columns=["asset_type", "weight"])
    col = _val_col(df)
    total = portfolio_total_value()
    alloc = df.groupby("asset_type")[col].sum().reset_index()
    alloc.rename(columns={col: "total_value"}, inplace=True)
    alloc["weight"] = alloc["total_value"] / total
    return alloc


def allocation_by_geography() -> pd.DataFrame:
    df = fetch_data()
    if df.empty:
        return pd.DataFrame(columns=["geography", "weight"])
    if "geography" not in df.columns:
        return pd.DataFrame(columns=["geography", "weight"])
    col = _val_col(df)
    total = portfolio_total_value()
    alloc = df.groupby("geography")[col].sum().reset_index()
    alloc.rename(columns={col: "total_value"}, inplace=True)
    alloc["weight"] = alloc["total_value"] / total
    return alloc


def allocation_by_currency() -> pd.DataFrame:
    df = fetch_data()
    if df.empty:
        return pd.DataFrame(columns=["currency", "weight"])
    col = _val_col(df)
    total = portfolio_total_value()
    alloc = df.groupby("currency")[col].sum().reset_index()
    alloc.rename(columns={col: "total_value"}, inplace=True)
    alloc["weight"] = alloc["total_value"] / total
    return alloc


def top_positions(n: int = 5) -> pd.DataFrame:
    df = fetch_data()
    if df.empty:
        return df
    return df.nlargest(n, "total_value")
