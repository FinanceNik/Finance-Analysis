import numpy as np
import Styles
import dataLoadPositions as dlp
from dash import dcc, html, dash_table


def _compute_currency_exposure():
    """Compute currency-level aggregation and concentration metrics.

    Returns
    -------
    positions_df : pd.DataFrame
        Per-position dataframe with market_value, cost_basis, unrealized_pnl, weight.
    by_currency_df : pd.DataFrame
        Grouped by currency with value, cost, pnl, weight columns.
    metrics : dict
        Summary metrics (num_currencies, chf_weight, largest_currency, hhi).
    """
    df = dlp.add_position_pnl_columns()
    if df.empty:
        return df, df, {}

    total_mv = df["market_value"].sum()
    if total_mv == 0:
        return df, df.head(0), {}

    df["weight"] = df["market_value"] / total_mv

    # --- Group by currency ---
    by_ccy = df.groupby("currency").agg(
        value=("market_value", "sum"),
        cost=("cost_basis", "sum"),
        pnl=("unrealized_pnl", "sum"),
    ).reset_index()
    by_ccy["weight"] = by_ccy["value"] / total_mv

    # --- Concentration: Herfindahl-Hirschman Index ---
    hhi = float(np.sum(by_ccy["weight"].values ** 2))

    # --- CHF exposure ---
    chf_row = by_ccy[by_ccy["currency"].str.upper() == "CHF"]
    chf_weight = float(chf_row["weight"].iloc[0]) if not chf_row.empty else 0.0

    # --- Largest currency ---
    largest_idx = by_ccy["value"].idxmax()
    largest_name = by_ccy.loc[largest_idx, "currency"]
    largest_weight = by_ccy.loc[largest_idx, "weight"]

    metrics = {
        "num_currencies": len(by_ccy),
        "chf_weight": chf_weight,
        "largest_currency": largest_name,
        "largest_weight": largest_weight,
        "hhi": hhi,
    }

    return df, by_ccy, metrics


def layout():
    df, by_ccy, metrics = _compute_currency_exposure()

    if df.empty or not metrics:
        return html.Div([
            html.Hr(),
            html.H4("No position data available."),
        ])

    # ── KPI row ──
    kpi_row = html.Div([
        Styles.kpiboxes(
            "Number of Currencies",
            metrics["num_currencies"],
            Styles.colorPalette[0],
        ),
        Styles.kpiboxes(
            "CHF Exposure %",
            f"{metrics['chf_weight']:.1%}",
            Styles.colorPalette[1],
        ),
        Styles.kpiboxes(
            "Largest Currency",
            f"{metrics['largest_currency']} ({metrics['largest_weight']:.1%})",
            Styles.colorPalette[2],
        ),
        Styles.kpiboxes(
            "FX Concentration (HHI)",
            f"{metrics['hhi']:.3f}",
            Styles.colorPalette[3],
        ),
    ])

    # ── Donut chart: currency allocation ──
    donut_chart = {
        "data": [{
            "type": "pie",
            "labels": by_ccy["currency"].tolist(),
            "values": by_ccy["weight"].tolist(),
            "hole": 0.55,
            "textinfo": "label+percent",
            "hoverinfo": "label+value+percent",
            "marker": {"colors": Styles.purple_list},
        }],
        "layout": Styles.graph_layout(title="Currency Allocation"),
    }

    # ── Horizontal bar chart: market value by currency ──
    by_ccy_sorted = by_ccy.sort_values("value", ascending=True)
    n_bars = len(by_ccy_sorted)
    bar_colors = (Styles.purple_list * ((n_bars // len(Styles.purple_list)) + 1))[:n_bars]

    bar_chart = {
        "data": [{
            "type": "bar",
            "x": by_ccy_sorted["value"].round(0).tolist(),
            "y": by_ccy_sorted["currency"].tolist(),
            "orientation": "h",
            "marker": {"color": bar_colors},
            "text": [f"{v:,.0f}" for v in by_ccy_sorted["value"]],
            "textposition": "outside",
        }],
        "layout": {
            **Styles.graph_layout(
                title="Market Value by Currency",
                xaxis={"title": "Market Value"},
                margin={"t": 40, "b": 40, "l": 80, "r": 80},
            ),
            "height": max(250, n_bars * 40),
        },
    }

    # ── Per-position FX exposure table ──
    table_df = df.copy()
    table_df["weight_pct"] = (table_df["weight"] * 100).round(2)
    table_df["fx_status"] = table_df["currency"].apply(
        lambda c: "Hedged" if str(c).upper() == "CHF" else "FX Exposed"
    )
    table_df["market_value"] = table_df["market_value"].round(2)

    display_cols = []
    col_map = {
        "symbol": ("Symbol", "text"),
        "currency": ("Currency", "text"),
        "market_value": ("Market Value", "numeric"),
        "weight_pct": ("Weight %", "numeric"),
        "fx_status": ("FX Status", "text"),
    }
    for col_id, (label, col_type) in col_map.items():
        if col_id in table_df.columns:
            display_cols.append({"name": label, "id": col_id, "type": col_type})

    fx_table = dash_table.DataTable(
        id="currency-exposure-table",
        columns=display_cols,
        data=table_df.to_dict("records"),
        sort_action="native",
        filter_action="native",
        page_size=20,
        style_table={"overflowX": "auto"},
        style_cell={"padding": "8px", "textAlign": "left", "fontSize": "14px"},
        style_header={
            "fontWeight": "bold",
            "fontSize": "14px",
            "fontFamily": Styles.GRAPH_LAYOUT["font"]["family"],
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f9f9f9"},
        ],
    )

    # ── Assemble layout ──
    return html.Div([
        html.Hr(),
        html.H4("Currency Exposure Analysis"),
        kpi_row,
        html.Hr(),

        # Donut + Bar side by side
        html.Div([
            dcc.Graph(id="currency-donut-chart", figure=donut_chart)
        ], className="card"),
        html.Div([
            dcc.Graph(id="currency-bar-chart", figure=bar_chart)
        ], className="card"),
        html.Hr(),

        # Table (full width)
        html.Div([
            fx_table,
        ], className="card", style={"marginBottom": "20px"}),
    ])
