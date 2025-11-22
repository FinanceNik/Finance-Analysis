import pandas as pd
from datetime import datetime

currentYear = int(datetime.today().strftime('%Y'))  # the current year
months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
filepath = "data/Positions_1640083_22112025_07_30.csv"

def fetch_data():
    df = pd.read_csv(filepath, sep=",")

    # --- Standardize column names ---
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
        .str.replace("#", "number")
        .str.replace("__", "_")
    )
    # --- Date column parsing ---
    for col in df.columns:
        # detect potential date columns
        if "date" in col:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    df_final = df.apply(lambda s: s.str.strip() if s.dtype == "object" else s)
    return df_final


def portfolio_total_value() -> float:
    df = fetch_data()
    return int(df["total_value"].sum())

def portfolio_cost_basis() -> float:
    df = fetch_data()
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
    df["market_value"] = df["quantity"] * df["price"]
    df["cost_basis"]   = df["quantity"] * df["unit_cost"]
    df["unrealized_pnl"] = df["market_value"] - df["cost_basis"]
    df["pnl_pct"] = df["unrealized_pnl"] / df["cost_basis"].replace(0, float("nan"))
    return df


def allocation_by_asset_type() -> pd.DataFrame:
    df = fetch_data()
    total = portfolio_total_value()
    alloc = df.groupby("asset_type")["total_value"].sum().reset_index()
    alloc["weight"] = alloc["total_value"] / total
    return alloc


def allocation_by_geography() -> pd.DataFrame:
    df = fetch_data()
    total = portfolio_total_value()
    alloc = df.groupby("geography")["total_value"].sum().reset_index()
    alloc["weight"] = alloc["total_value"] / total
    return alloc


def top_positions(n: int = 5) -> pd.DataFrame:
    df = fetch_data()
    return df.nlargest(n, "total_value")

