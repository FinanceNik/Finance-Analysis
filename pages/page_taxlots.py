import pandas as pd
from dash import dcc, html, dash_table
import Styles
import dataLoadTransactions as dlt
import dataLoadPositions as dlp


def _compute_tax_lots():
    """Compute FIFO-based tax lots from transaction history."""
    txn = dlt.ingest_transactions()
    positions = dlp.fetch_data()

    if txn.empty:
        return pd.DataFrame(), {}

    # Filter to buy transactions
    buys = txn[txn["transaction"].str.lower().isin(["buy", "crypto deposit"])].copy()
    if buys.empty or "symbol" not in buys.columns:
        return pd.DataFrame(), {}

    buys = buys.dropna(subset=["symbol", "quantity", "unit_price"])
    buys = buys[buys["quantity"] > 0].copy()
    buys = buys.sort_values("date")

    # Get current prices from positions
    price_map = {}
    if not positions.empty and "symbol" in positions.columns and "price" in positions.columns:
        price_map = dict(zip(positions["symbol"], positions["price"]))

    lots = []
    for _, row in buys.iterrows():
        symbol = row["symbol"]
        qty = row["quantity"]
        cost = row["unit_price"]
        date = row["date"]
        current_price = price_map.get(symbol, cost)

        market_value = qty * current_price
        cost_basis = qty * cost
        gain_loss = market_value - cost_basis
        gain_pct = gain_loss / cost_basis if cost_basis != 0 else 0

        lots.append({
            "date": date.strftime("%Y-%m-%d") if pd.notna(date) else "",
            "symbol": symbol,
            "quantity": round(qty, 4),
            "cost_per_unit": round(cost, 2),
            "cost_basis": round(cost_basis, 2),
            "current_price": round(current_price, 2),
            "market_value": round(market_value, 2),
            "gain_loss": round(gain_loss, 2),
            "gain_pct": round(gain_pct * 100, 1),
        })

    if not lots:
        return pd.DataFrame(), {}

    lots_df = pd.DataFrame(lots)

    # Summary metrics
    total_cost = lots_df["cost_basis"].sum()
    total_mv = lots_df["market_value"].sum()
    total_gl = lots_df["gain_loss"].sum()
    gainers = lots_df[lots_df["gain_loss"] > 0]["gain_loss"].sum()
    losers = lots_df[lots_df["gain_loss"] < 0]["gain_loss"].sum()

    summary = {
        "total_cost": round(total_cost, 2),
        "total_mv": round(total_mv, 2),
        "total_gl": round(total_gl, 2),
        "gainers": round(gainers, 2),
        "losers": round(losers, 2),
    }

    return lots_df, summary


def layout():
    lots_df, summary = _compute_tax_lots()

    if lots_df.empty:
        return html.Div([
            html.Hr(),
            html.H4("Tax-Lot Analysis"),
            html.P("No purchase transactions found in transaction history."),
        ])

    # KPI row
    kpis = html.Div([
        Styles.kpiboxes("Total Cost Basis", f"{summary['total_cost']:,.0f}", Styles.colorPalette[0]),
        Styles.kpiboxes("Total Market Value", f"{summary['total_mv']:,.0f}", Styles.colorPalette[1]),
        Styles.kpiboxes("Total Gains", f"{summary['gainers']:,.0f}", Styles.strongGreen),
        Styles.kpiboxes("Total Losses", f"{summary['losers']:,.0f}", Styles.strongRed),
    ])

    # Data table
    columns = [
        {"name": "Date", "id": "date"},
        {"name": "Symbol", "id": "symbol"},
        {"name": "Qty", "id": "quantity", "type": "numeric"},
        {"name": "Cost/Unit", "id": "cost_per_unit", "type": "numeric"},
        {"name": "Cost Basis", "id": "cost_basis", "type": "numeric"},
        {"name": "Cur. Price", "id": "current_price", "type": "numeric"},
        {"name": "Mkt Value", "id": "market_value", "type": "numeric"},
        {"name": "Gain/Loss", "id": "gain_loss", "type": "numeric"},
        {"name": "G/L %", "id": "gain_pct", "type": "numeric"},
    ]

    table = dash_table.DataTable(
        id="tax-lots-table",
        columns=columns,
        data=lots_df.to_dict("records"),
        sort_action="native",
        filter_action="native",
        page_size=25,
        style_table={"overflowX": "auto"},
        style_cell={"padding": "8px", "textAlign": "left", "fontSize": "13px"},
        style_header={"fontWeight": "bold", "fontSize": "13px",
                       "fontFamily": Styles.GRAPH_LAYOUT['font']['family']},
        style_data_conditional=[
            {"if": {"filter_query": "{gain_loss} > 0", "column_id": "gain_loss"},
             "backgroundColor": "#e6ffe6", "color": "green"},
            {"if": {"filter_query": "{gain_loss} < 0", "column_id": "gain_loss"},
             "backgroundColor": "#ffe6e6", "color": "red"},
            {"if": {"filter_query": "{gain_pct} > 0", "column_id": "gain_pct"},
             "color": "green"},
            {"if": {"filter_query": "{gain_pct} < 0", "column_id": "gain_pct"},
             "color": "red"},
            {"if": {"row_index": "odd"}, "backgroundColor": "#f9f9f9"},
        ],
    )

    # Gain/loss by symbol chart
    by_symbol = lots_df.groupby("symbol").agg(
        total_gl=("gain_loss", "sum"),
        total_cost=("cost_basis", "sum"),
    ).reset_index()
    by_symbol["gl_pct"] = (by_symbol["total_gl"] / by_symbol["total_cost"] * 100).round(1)
    by_symbol = by_symbol.sort_values("total_gl")

    colors = [Styles.strongGreen if v >= 0 else Styles.strongRed for v in by_symbol["total_gl"]]

    gl_chart = {
        'data': [{
            'type': 'bar',
            'x': by_symbol['total_gl'].tolist(),
            'y': by_symbol['symbol'].tolist(),
            'orientation': 'h',
            'marker': {'color': colors},
            'text': [f"{v:+,.0f} ({p:+.1f}%)" for v, p in zip(by_symbol['total_gl'], by_symbol['gl_pct'])],
            'textposition': 'outside',
        }],
        'layout': Styles.graph_layout(
            title='FIFO Gain/Loss by Symbol',
            xaxis={'title': 'Gain/Loss'},
            margin={'l': 100, 'r': 100},
            height=max(300, len(by_symbol) * 30),
        )
    }

    return html.Div([
        html.Hr(),
        html.H4("Tax-Lot Analysis (FIFO)"),
        kpis,
        html.Hr(),

        html.Div([
            dcc.Graph(id='tax-lot-gl-chart', figure=gl_chart)
        ], className="card", style=Styles.STYLE(100)),
        html.Hr(),

        html.H5("Individual Tax Lots"),
        html.Div([table], className="card", style={**Styles.STYLE(100), "marginBottom": "20px"}),
    ])
