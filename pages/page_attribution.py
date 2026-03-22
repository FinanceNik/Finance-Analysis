"""
Performance Attribution page — Brinson-style attribution analysis.

Decomposes portfolio excess return vs benchmark (SPY) into:
  - Allocation effect   (over/underweight sectors)
  - Selection effect     (stock picking within sectors)
  - Interaction effect   (combined)
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output
import Styles
import config
import dataLoadPositions as dlp


# ── Approximate S&P 500 sector weights (SPY benchmark) ──
_SPY_SECTOR_WEIGHTS = {
    "Technology":     0.32,
    "Financials":     0.13,
    "Healthcare":     0.12,
    "Consumer Disc.": 0.10,
    "Industrials":    0.09,
    "Comm. Services": 0.08,
    "Consumer Stap.": 0.06,
    "Energy":         0.04,
    "Utilities":      0.02,
    "Real Estate":    0.02,
    "Materials":      0.02,
}

# Sectors in the portfolio that don't exist in SPY
_NON_SPY_SECTORS = {"Crypto", "Diversified"}


def _load_symbol_mapping() -> dict:
    """Load broker-symbol to Yahoo-ticker mapping from mapping.csv."""
    try:
        mapping = pd.read_csv("data/mapping.csv", sep=",")
        return dict(zip(mapping["symbol"], mapping["ticker"]))
    except Exception:
        return {}


def _resolve_symbol(sym, available_cols, sym_to_ticker=None):
    """Resolve a broker symbol to a historical data column name."""
    if sym in available_cols:
        return sym
    if sym_to_ticker and sym_to_ticker.get(sym) and sym_to_ticker[sym] in available_cols:
        return sym_to_ticker[sym]
    matches = [c for c in available_cols if c.startswith(sym)]
    return matches[0] if matches else None


def _compute_attribution():
    """
    Compute Brinson-style attribution for each sector.

    Returns
    -------
    attr_df : DataFrame with columns:
        sector, port_weight, bench_weight, port_return, bench_return,
        allocation, selection, interaction
    summary : dict with total_alpha, total_alloc, total_select, total_inter, best_sector
    """
    df = dlp.add_position_pnl_columns()
    if df.empty:
        return pd.DataFrame(), {}

    total_mv = df["market_value"].sum()
    if total_mv == 0:
        return pd.DataFrame(), {}

    df["weight"] = df["market_value"] / total_mv

    # Map each holding to its sector via config.SECTOR_MAP
    df["sector"] = df["symbol"].map(config.SECTOR_MAP).fillna("Other")

    # ── Per-holding return from cost basis ──
    df["holding_return"] = df["pnl_pct"].fillna(0.0)

    # ── Aggregate by sector ──
    sector_agg = df.groupby("sector").agg(
        port_weight=("weight", "sum"),
        weighted_return=("weight", lambda w: 0.0),  # placeholder
    ).reset_index()

    # Compute weight-weighted sector returns
    sector_returns = {}
    for sector, grp in df.groupby("sector"):
        sw = grp["weight"].sum()
        if sw > 0:
            sector_returns[sector] = (grp["weight"] * grp["holding_return"]).sum() / sw
        else:
            sector_returns[sector] = 0.0
    sector_agg["port_return"] = sector_agg["sector"].map(sector_returns)

    # ── Load historical data for benchmark sector return proxy ──
    bench_sector_returns = _estimate_benchmark_returns()

    # ── Build benchmark weight column ──
    all_sectors = set(sector_agg["sector"].tolist()) | set(_SPY_SECTOR_WEIGHTS.keys())
    rows = []
    for sector in sorted(all_sectors):
        pw = sector_agg.loc[sector_agg["sector"] == sector, "port_weight"]
        pw = float(pw.iloc[0]) if len(pw) > 0 else 0.0
        pr = sector_agg.loc[sector_agg["sector"] == sector, "port_return"]
        pr = float(pr.iloc[0]) if len(pr) > 0 else 0.0
        bw = _SPY_SECTOR_WEIGHTS.get(sector, 0.0)
        br = bench_sector_returns.get(sector, 0.0)
        rows.append({
            "sector": sector,
            "port_weight": pw,
            "bench_weight": bw,
            "port_return": pr,
            "bench_return": br,
        })

    attr_df = pd.DataFrame(rows)

    # Remove sectors where both portfolio and benchmark have zero weight
    attr_df = attr_df[
        (attr_df["port_weight"] > 0) | (attr_df["bench_weight"] > 0)
    ].copy()

    # ── Brinson decomposition ──
    total_bench_return = (attr_df["bench_weight"] * attr_df["bench_return"]).sum()

    attr_df["allocation"] = (
        (attr_df["port_weight"] - attr_df["bench_weight"]) *
        (attr_df["bench_return"] - total_bench_return)
    )
    attr_df["selection"] = (
        attr_df["bench_weight"] *
        (attr_df["port_return"] - attr_df["bench_return"])
    )
    attr_df["interaction"] = (
        (attr_df["port_weight"] - attr_df["bench_weight"]) *
        (attr_df["port_return"] - attr_df["bench_return"])
    )

    total_alloc = attr_df["allocation"].sum()
    total_select = attr_df["selection"].sum()
    total_inter = attr_df["interaction"].sum()
    total_alpha = total_alloc + total_select + total_inter

    # Best sector bet = sector with highest combined contribution
    attr_df["total_effect"] = attr_df["allocation"] + attr_df["selection"] + attr_df["interaction"]
    best_idx = attr_df["total_effect"].idxmax() if not attr_df.empty else None
    best_sector = attr_df.loc[best_idx, "sector"] if best_idx is not None else "N/A"

    summary = {
        "total_alpha": total_alpha,
        "total_alloc": total_alloc,
        "total_select": total_select,
        "total_inter": total_inter,
        "best_sector": best_sector,
    }

    attr_df = attr_df.sort_values("total_effect", ascending=False).reset_index(drop=True)
    return attr_df, summary


def _estimate_benchmark_returns():
    """
    Estimate benchmark (SPY-proxy) sector returns using historical data.

    Falls back to a flat estimate if historical data is unavailable.
    """
    bench_returns = {}
    try:
        hist = dlp.load_historical_data().reset_index()
        if "date" in hist.columns:
            hist = hist.set_index("date")
        hist = 10 ** hist
        hist = hist.groupby(hist.index).first().sort_index().ffill()

        # Use SPY as benchmark total return proxy
        sym_to_ticker = _load_symbol_mapping()
        spy_col = _resolve_symbol("SPY", hist.columns, sym_to_ticker)
        if spy_col and spy_col in hist.columns:
            spy_prices = hist[spy_col].dropna()
            if len(spy_prices) >= 2:
                spy_total_ret = (spy_prices.iloc[-1] / spy_prices.iloc[0]) - 1
                # Approximate: each SPY sector gets the same total return
                for sector in _SPY_SECTOR_WEIGHTS:
                    bench_returns[sector] = spy_total_ret
                # Non-SPY sectors get 0 benchmark return
                for sector in _NON_SPY_SECTORS:
                    bench_returns[sector] = 0.0
                return bench_returns
    except Exception:
        pass

    # Fallback: assume 10% annualized for SPY sectors
    for sector in _SPY_SECTOR_WEIGHTS:
        bench_returns[sector] = 0.10
    for sector in _NON_SPY_SECTORS:
        bench_returns[sector] = 0.0
    return bench_returns


def _build_waterfall(summary):
    """Waterfall chart: Total Return decomposition."""
    labels = ["Allocation", "Selection", "Interaction", "Total Alpha"]
    values = [
        summary.get("total_alloc", 0),
        summary.get("total_select", 0),
        summary.get("total_inter", 0),
        summary.get("total_alpha", 0),
    ]
    measures = ["relative", "relative", "relative", "total"]
    colors = [
        Styles.strongGreen if v >= 0 else Styles.strongRed
        for v in values
    ]

    fig = go.Figure(go.Waterfall(
        x=labels,
        y=[v * 100 for v in values],
        measure=measures,
        textposition="outside",
        text=[f"{v * 100:+.2f}%" for v in values],
        connector={"line": {"color": "rgba(128,128,128,0.3)"}},
        increasing={"marker": {"color": Styles.strongGreen}},
        decreasing={"marker": {"color": Styles.strongRed}},
        totals={"marker": {"color": "#008DD5"}},
    ))
    fig.update_layout(
        **Styles.graph_layout(
            title="Return Attribution Waterfall",
            yaxis_title="Contribution (%)",
            showlegend=False,
            margin={"t": 50, "b": 40, "l": 60, "r": 30},
        )
    )
    return fig


def _build_sector_bar(attr_df):
    """Stacked bar chart by sector: allocation vs selection contribution."""
    if attr_df.empty:
        return go.Figure()

    sectors = attr_df["sector"].tolist()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sectors,
        y=[v * 100 for v in attr_df["allocation"]],
        name="Allocation",
        marker_color="#008DD5",
    ))
    fig.add_trace(go.Bar(
        x=sectors,
        y=[v * 100 for v in attr_df["selection"]],
        name="Selection",
        marker_color="#F56476",
    ))
    fig.add_trace(go.Bar(
        x=sectors,
        y=[v * 100 for v in attr_df["interaction"]],
        name="Interaction",
        marker_color="#A8A4CE",
    ))

    fig.update_layout(
        **Styles.graph_layout(
            title="Attribution by Sector",
            barmode="group",
            yaxis_title="Contribution (%)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin={"t": 60, "b": 60, "l": 60, "r": 30},
        )
    )
    return fig


def _build_summary_table(attr_df):
    """HTML summary table of attribution data."""
    if attr_df.empty:
        return html.Div("No attribution data available.", className="text-muted")

    header = html.Thead(html.Tr([
        html.Th("Sector"),
        html.Th("Port Wt", style={"textAlign": "right"}),
        html.Th("Bench Wt", style={"textAlign": "right"}),
        html.Th("Port Ret", style={"textAlign": "right"}),
        html.Th("Bench Ret", style={"textAlign": "right"}),
        html.Th("Allocation", style={"textAlign": "right"}),
        html.Th("Selection", style={"textAlign": "right"}),
        html.Th("Total", style={"textAlign": "right"}),
    ]))

    rows = []
    for _, r in attr_df.iterrows():
        total_eff = r["allocation"] + r["selection"] + r["interaction"]
        total_color = Styles.strongGreen if total_eff >= 0 else Styles.strongRed
        rows.append(html.Tr([
            html.Td(r["sector"]),
            html.Td(f"{r['port_weight']:.1%}", style={"textAlign": "right"}),
            html.Td(f"{r['bench_weight']:.1%}", style={"textAlign": "right"}),
            html.Td(f"{r['port_return']:.1%}", style={"textAlign": "right"}),
            html.Td(f"{r['bench_return']:.1%}", style={"textAlign": "right"}),
            html.Td(f"{r['allocation'] * 100:+.2f}%", style={"textAlign": "right"}),
            html.Td(f"{r['selection'] * 100:+.2f}%", style={"textAlign": "right"}),
            html.Td(
                f"{total_eff * 100:+.2f}%",
                style={"textAlign": "right", "color": total_color, "fontWeight": "600"},
            ),
        ]))

    # Total row
    t_alloc = attr_df["allocation"].sum()
    t_select = attr_df["selection"].sum()
    t_inter = attr_df["interaction"].sum()
    t_total = t_alloc + t_select + t_inter
    t_color = Styles.strongGreen if t_total >= 0 else Styles.strongRed
    rows.append(html.Tr([
        html.Td("Total", style={"fontWeight": "700"}),
        html.Td(f"{attr_df['port_weight'].sum():.1%}", style={"textAlign": "right", "fontWeight": "700"}),
        html.Td(f"{attr_df['bench_weight'].sum():.1%}", style={"textAlign": "right", "fontWeight": "700"}),
        html.Td("", style={"textAlign": "right"}),
        html.Td("", style={"textAlign": "right"}),
        html.Td(f"{t_alloc * 100:+.2f}%", style={"textAlign": "right", "fontWeight": "700"}),
        html.Td(f"{t_select * 100:+.2f}%", style={"textAlign": "right", "fontWeight": "700"}),
        html.Td(
            f"{t_total * 100:+.2f}%",
            style={"textAlign": "right", "color": t_color, "fontWeight": "700"},
        ),
    ], className="table-total-row"))

    return html.Table([header, html.Tbody(rows)], className="table")


# ═══════════════════════════════════════════════════════════════════
# Layout
# ═══════════════════════════════════════════════════════════════════

def layout():
    attr_df, summary = _compute_attribution()

    if not summary:
        return html.Div([
            html.H4("Performance Attribution"),
            html.P("No position data available. Load positions to see attribution analysis.",
                   className="text-muted"),
        ])

    total_alpha = summary.get("total_alpha", 0)
    total_alloc = summary.get("total_alloc", 0)
    total_select = summary.get("total_select", 0)
    best_sector = summary.get("best_sector", "N/A")

    alpha_color = Styles.strongGreen if total_alpha >= 0 else Styles.strongRed
    alloc_color = Styles.strongGreen if total_alloc >= 0 else Styles.strongRed
    select_color = Styles.strongGreen if total_select >= 0 else Styles.strongRed

    kpis = html.Div([
        Styles.kpiboxes("Total Alpha", f"{total_alpha * 100:+.2f}%", alpha_color),
        Styles.kpiboxes("Allocation Effect", f"{total_alloc * 100:+.2f}%", alloc_color),
        Styles.kpiboxes("Selection Effect", f"{total_select * 100:+.2f}%", select_color),
        Styles.kpiboxes("Best Sector Bet", best_sector, "#008DD5"),
    ], className="kpi-row")

    waterfall = html.Div(
        dcc.Graph(figure=_build_waterfall(summary), config={"displayModeBar": False}),
        className="card",
    )

    sector_bar = html.Div(
        dcc.Graph(figure=_build_sector_bar(attr_df), config={"displayModeBar": False}),
        className="card",
    )

    table = html.Div(
        _build_summary_table(attr_df),
        className="card", style={"padding": "16px", "overflowX": "auto"},
    )

    return html.Div([
        kpis,
        html.Div([waterfall, sector_bar], className="grid-2"),
        html.H5("Sector Attribution Detail",
                 style={"marginTop": "24px", "marginBottom": "12px"}),
        table,
    ])


# ═══════════════════════════════════════════════════════════════════
# Callbacks
# ═══════════════════════════════════════════════════════════════════

def register_callbacks(app):
    """No interactive callbacks needed — page is static on load."""
    pass
