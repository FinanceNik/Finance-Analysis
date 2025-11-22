import pandas as pd
import pathlib


def ingest_portfolio_file(
        filepath: str = "data/Positions_1640083_22112025_07_30.csv"
) -> pd.DataFrame:

    # Ensure path exists
    file_path = pathlib.Path(filepath)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    # Read CSV
    df = pd.read_csv(file_path)

    # --- Standardize column names ---
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )

    # --- Attempt to convert numeric-like columns ---
    for col in df.columns:
        # try numeric conversion where it makes sense
        df[col] = pd.to_numeric(df[col])

    # --- Date column parsing ---
    for col in df.columns:
        # detect potential date columns
        if "date" in col:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # --- Strip string columns ---
    df = df.apply(
        lambda s: s.str.strip() if s.dtype == "object" else s
    )

    return df

# ---------------------------------------------------------------------
# Basic KPI calculations
# ---------------------------------------------------------------------

def portfolio_total_value(df: pd.DataFrame) -> float:
    """
    Returns the total market value of the portfolio.
    """
    return df["total_value"].sum()


def portfolio_cost_basis(df: pd.DataFrame) -> float:
    """
    Returns the total invested capital (sum of quantity * unit_cost).
    """
    return (df["quantity"] * df["unit_cost"]).sum()


def portfolio_unrealized_pnl(df: pd.DataFrame) -> float:
    """
    Returns total unrealized profit/loss.
    """
    mv = portfolio_total_value(df)
    cost = portfolio_cost_basis(df)
    return mv - cost


def portfolio_return_pct(df: pd.DataFrame) -> float:
    """
    Portfolio unrealized return % (unrealized PnL / cost basis).
    """
    cost = portfolio_cost_basis(df)
    if cost == 0:
        return 0.0
    return portfolio_unrealized_pnl(df) / cost


# ---------------------------------------------------------------------
# Position-level KPIs
# ---------------------------------------------------------------------

def add_position_pnl_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds per-position market_value, cost_basis, unrealized_pnl, and pnl_pct.
    """
    df = df.copy()

    df["market_value"] = df["quantity"] * df["price"]
    df["cost_basis"]   = df["quantity"] * df["unit_cost"]
    df["unrealized_pnl"] = df["market_value"] - df["cost_basis"]
    df["pnl_pct"] = df["unrealized_pnl"] / df["cost_basis"].replace(0, float("nan"))

    return df


# ---------------------------------------------------------------------
# Allocation metrics
# ---------------------------------------------------------------------

def allocation_by_asset_type(df: pd.DataFrame) -> pd.DataFrame:
    """
    Allocation by asset type.
    """
    total = portfolio_total_value(df)
    alloc = df.groupby("asset_type")["total_value"].sum().reset_index()
    alloc["weight"] = alloc["total_value"] / total
    return alloc


def allocation_by_geography(df: pd.DataFrame) -> pd.DataFrame:
    """
    Allocation by geography.
    """
    total = portfolio_total_value(df)
    alloc = df.groupby("geography")["total_value"].sum().reset_index()
    alloc["weight"] = alloc["total_value"] / total
    return alloc


def top_positions(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """
    Returns top N positions by total value.
    """
    return df.nlargest(n, "total_value")
