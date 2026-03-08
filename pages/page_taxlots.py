import pandas as pd
from datetime import datetime
from dash import dcc, html, dash_table, Input, Output
import Styles
import dataLoadTransactions as dlt
import dataLoadPositions as dlp


def _compute_tax_lots(method="fifo"):
    """Compute tax lots from transaction history using the specified cost basis method.

    Parameters
    ----------
    method : str
        "fifo" sorts buys by date ascending (first-in, first-out).
        "hifo" sorts buys by unit_price descending (highest-in, first-out).
    """
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

    # Sort according to cost basis method
    if method == "hifo":
        buys = buys.sort_values("unit_price", ascending=False)
    else:
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

        # Holding period calculation
        hold_days = (datetime.today() - date).days if pd.notna(date) else 0
        holding_period = "Long-Term" if hold_days > 365 else "Short-Term"

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
            "holding_period": holding_period,
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

    # Short-term / long-term breakdown
    st_mask = lots_df["holding_period"] == "Short-Term"
    lt_mask = lots_df["holding_period"] == "Long-Term"
    st_gains = lots_df.loc[st_mask, "gain_loss"].sum()
    lt_gains = lots_df.loc[lt_mask, "gain_loss"].sum()

    summary = {
        "total_cost": round(total_cost, 2),
        "total_mv": round(total_mv, 2),
        "total_gl": round(total_gl, 2),
        "gainers": round(gainers, 2),
        "losers": round(losers, 2),
        "st_gains": round(st_gains, 2),
        "lt_gains": round(lt_gains, 2),
    }

    return lots_df, summary


def _detect_wash_sales(txn):
    """Detect potential wash sales: sells followed by a rebuy of the same symbol within 30 days."""
    warnings = []
    if txn.empty or "transaction" not in txn.columns:
        return warnings

    sells = txn[txn["transaction"].str.lower() == "sell"].copy()
    buys = txn[txn["transaction"].str.lower().isin(["buy", "crypto deposit"])].copy()

    if sells.empty or buys.empty:
        return warnings

    for _, sell_row in sells.iterrows():
        symbol = sell_row.get("symbol")
        sell_date = sell_row.get("date")
        if pd.isna(symbol) or pd.isna(sell_date):
            continue

        # Check for rebuys of same symbol within 30 days after the sell
        symbol_buys = buys[buys["symbol"] == symbol].copy()
        if symbol_buys.empty:
            continue

        for _, buy_row in symbol_buys.iterrows():
            buy_date = buy_row.get("date")
            if pd.isna(buy_date):
                continue
            delta = (buy_date - sell_date).days
            if 0 < delta <= 30:
                warnings.append({
                    "symbol": symbol,
                    "sell_date": sell_date.strftime("%Y-%m-%d") if pd.notna(sell_date) else "",
                    "rebuy_date": buy_date.strftime("%Y-%m-%d") if pd.notna(buy_date) else "",
                    "days_apart": delta,
                })
                break  # One warning per sell is enough

    return warnings


def layout():
    return html.Div([
        html.Hr(),
        html.H4("Tax-Lot Analysis"),

        # Controls row
        html.Div([
            html.Div([
                html.Label("Cost Basis Method"),
                dcc.RadioItems(
                    id="cost-method-toggle",
                    options=[
                        {"label": " FIFO", "value": "fifo"},
                        {"label": " HIFO", "value": "hifo"},
                    ],
                    value="fifo", inline=True,
                    style={"fontSize": "14px"},
                ),
            ], style={"display": "inline-block", "padding": "10px 20px"}),
            html.Div([
                html.Label("Tax Rate (%)"),
                dcc.Input(id="tax-rate-input", type="number", value=25, min=0, max=50,
                          style={"width": "70px", "padding": "6px"}),
            ], style={"display": "inline-block", "padding": "10px 20px"}),
        ]),

        html.Hr(),

        # Dynamic results container
        html.Div(id="taxlot-results"),
    ])


def register_callbacks(app):
    @app.callback(
        Output("taxlot-results", "children"),
        [Input("cost-method-toggle", "value"),
         Input("tax-rate-input", "value")]
    )
    def update_taxlots(method, tax_rate):
        method = method or "fifo"
        tax_rate = tax_rate or 25

        lots_df, summary = _compute_tax_lots(method)

        if lots_df.empty:
            return html.P("No purchase transactions found in transaction history.")

        method_label = "FIFO" if method == "fifo" else "HIFO"

        # ── KPI row ──
        kpis = html.Div([
            Styles.kpiboxes("Total Cost Basis", f"{summary['total_cost']:,.0f}", Styles.colorPalette[0]),
            Styles.kpiboxes("Total Market Value", f"{summary['total_mv']:,.0f}", Styles.colorPalette[1]),
            Styles.kpiboxes("Total Gains", f"{summary['gainers']:,.0f}", Styles.strongGreen),
            Styles.kpiboxes("Total Losses", f"{summary['losers']:,.0f}", Styles.strongRed),
            Styles.kpiboxes("Short-Term G/L", f"{summary['st_gains']:,.0f}", Styles.colorPalette[2]),
            Styles.kpiboxes("Long-Term G/L", f"{summary['lt_gains']:,.0f}", Styles.colorPalette[3]),
        ])

        # ── Gain/loss by symbol chart ──
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
                title=f'{method_label} Gain/Loss by Symbol',
                xaxis={'title': 'Gain/Loss'},
                margin={'l': 100, 'r': 100},
                height=max(300, len(by_symbol) * 30),
            )
        }

        # ── Data table ──
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
            {"name": "Holding", "id": "holding_period"},
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
            style_header={"backgroundColor": Styles.colorPalette[0], "color": "white",
                           "fontWeight": "bold", "fontSize": "13px",
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

        # ── Tax-loss harvesting section ──
        harvest_candidates = lots_df[lots_df["gain_pct"] < -5.0]
        if not harvest_candidates.empty:
            total_losses = harvest_candidates["gain_loss"].sum()
            potential_savings = abs(total_losses) * tax_rate / 100
            harvest_symbols = ", ".join(harvest_candidates["symbol"].unique())

            harvesting_section = html.Div([
                html.H5("Tax-Loss Harvesting Opportunities",
                         style={"color": Styles.strongRed}),
                html.P(f"Symbols with losses > 5%: {harvest_symbols}"),
                html.P(f"Total harvestable losses: {total_losses:,.2f}"),
                html.P(f"Potential tax savings at {tax_rate}%: {potential_savings:,.2f}",
                       style={"fontWeight": "bold", "fontSize": "16px"}),
            ], style={
                "padding": "16px",
                "border": f"2px solid {Styles.strongRed}",
                "borderRadius": "8px",
                "backgroundColor": "#fff5f5",
                "marginBottom": "20px",
            })
        else:
            harvesting_section = html.Div([
                html.H5("Tax-Loss Harvesting"),
                html.P("No tax-loss harvesting opportunities (no lots with > 5% loss)."),
            ], style={"padding": "16px", "marginBottom": "20px"})

        # ── Wash sale detection ──
        txn = dlt.ingest_transactions()
        wash_warnings = _detect_wash_sales(txn)
        if wash_warnings:
            badges = []
            for w in wash_warnings:
                badges.append(
                    html.Span(
                        f"  {w['symbol']}: sold {w['sell_date']}, rebought {w['rebuy_date']} "
                        f"({w['days_apart']}d)  ",
                        style={
                            "backgroundColor": "#ff9500",
                            "color": "white",
                            "padding": "4px 10px",
                            "borderRadius": "12px",
                            "fontSize": "13px",
                            "marginRight": "8px",
                            "display": "inline-block",
                            "marginBottom": "4px",
                        },
                    )
                )
            wash_section = html.Div([
                html.H5("Wash Sale Warnings", style={"color": "#ff9500"}),
                html.Div(badges),
            ], style={"padding": "16px", "marginBottom": "20px"})
        else:
            wash_section = html.Div([
                html.H5("Wash Sale Detection"),
                html.P("No wash sale violations detected."),
            ], style={"padding": "16px", "marginBottom": "20px"})

        # ── Assemble full output ──
        return html.Div([
            kpis,
            html.Hr(),

            html.Div([
                dcc.Graph(id='tax-lot-gl-chart', figure=gl_chart)
            ], className="card", style=Styles.STYLE(100)),
            html.Hr(),

            harvesting_section,
            wash_section,
            html.Hr(),

            html.H5("Individual Tax Lots"),
            html.Div([table], className="card", style={**Styles.STYLE(100), "marginBottom": "20px"}),
        ])
