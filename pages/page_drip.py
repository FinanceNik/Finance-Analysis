import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dash import dcc, html, dash_table, Input, Output
import Styles
import dataLoadTransactions as dlt
import dataLoadPositions as dlp


# ─────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────

def _get_portfolio_stats():
    """Return current portfolio value and estimated dividend yield."""
    positions = dlp.fetch_data()
    portfolio_value = 0
    dividend_yield = 0.05  # fallback default

    if not positions.empty and "total_value" in positions.columns:
        portfolio_value = positions["total_value"].sum()

    # Compute TTM yield from actual dividend history
    txn = dlt.ingest_transactions()
    if not txn.empty and "transaction" in txn.columns:
        dividends = txn[txn["transaction"].str.lower() == "dividend"].copy()
        if not dividends.empty:
            if "net_amount" in dividends.columns:
                dividends["amount"] = dividends["net_amount"].abs()
            today = datetime.today()
            ttm_start = today - timedelta(days=365)
            ttm_total = dividends[dividends["date"] >= ttm_start]["amount"].sum()
            if portfolio_value > 0 and ttm_total > 0:
                dividend_yield = ttm_total / portfolio_value

    return portfolio_value, dividend_yield


def _simulate_drip(portfolio_value, dividend_yield, div_growth_rate,
                   price_appreciation, years):
    """Simulate DRIP vs No-DRIP over the given time horizon.

    Returns a list of dicts with annual breakdown data.
    """
    rows = []

    # DRIP scenario: dividends buy more shares, compounding
    drip_value = portfolio_value
    # No-DRIP scenario: shares stay fixed, dividends accumulate as cash
    no_drip_share_value = portfolio_value
    no_drip_cash = 0.0
    cumulative_dividends = 0.0

    current_yield = dividend_yield

    for year in range(1, years + 1):
        # Dividends earned this year
        drip_dividends = drip_value * current_yield
        no_drip_dividends = no_drip_share_value * current_yield

        cumulative_dividends += no_drip_dividends

        # DRIP: reinvest dividends, then appreciate
        drip_value = (drip_value + drip_dividends) * (1 + price_appreciation)

        # No-DRIP: only share value appreciates, cash accumulates
        no_drip_share_value = no_drip_share_value * (1 + price_appreciation)
        no_drip_cash += no_drip_dividends

        no_drip_total = no_drip_share_value + no_drip_cash

        advantage_dollar = drip_value - no_drip_total
        advantage_pct = (advantage_dollar / no_drip_total * 100) if no_drip_total > 0 else 0

        rows.append({
            "year": year,
            "drip_value": round(drip_value, 2),
            "no_drip_value": round(no_drip_total, 2),
            "no_drip_shares": round(no_drip_share_value, 2),
            "no_drip_cash": round(no_drip_cash, 2),
            "dividend_income": round(no_drip_dividends, 2),
            "cumulative_dividends": round(cumulative_dividends, 2),
            "advantage_dollar": round(advantage_dollar, 2),
            "advantage_pct": round(advantage_pct, 2),
        })

        # Grow the dividend yield for next year
        current_yield *= (1 + div_growth_rate)

    return rows


# ─────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────

def layout():
    portfolio_value, dividend_yield = _get_portfolio_stats()

    return html.Div([
        html.H4("DRIP Simulator"),
        html.P("Compare dividend reinvestment (DRIP) vs taking dividends as cash. "
               "Uses your current portfolio value and estimated dividend yield.",
               style={"fontSize": "13px", "color": "var(--text-muted, #888)",
                      "margin": "0 0 16px 0"}),

        # ── Inputs ──
        html.Div([
            html.Div([
                html.Label("Time Horizon (years)"),
                dcc.Slider(
                    id="drip-horizon",
                    min=5, max=30, step=5, value=20,
                    marks={5: "5", 10: "10", 15: "15", 20: "20", 25: "25", 30: "30"},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ], style={"flex": "1", "padding": "10px 20px"}),
            html.Div([
                html.Label("Dividend Growth Rate (% p.a.)"),
                dcc.Input(
                    id="drip-div-growth",
                    type="number", value=5.0, step=0.5, min=0, max=20,
                    style={"width": "100px", "padding": "6px 10px",
                           "borderRadius": "8px",
                           "border": "1px solid var(--border-color, #ddd)"},
                ),
            ], style={"flex": "1", "padding": "10px 20px"}),
            html.Div([
                html.Label("Price Appreciation (% p.a.)"),
                dcc.Input(
                    id="drip-price-growth",
                    type="number", value=7.0, step=0.5, min=0, max=25,
                    style={"width": "100px", "padding": "6px 10px",
                           "borderRadius": "8px",
                           "border": "1px solid var(--border-color, #ddd)"},
                ),
            ], style={"flex": "1", "padding": "10px 20px"}),
        ], style={"display": "flex", "flexWrap": "wrap", "marginBottom": "16px"}),

        # ── Dynamic output ──
        dcc.Loading(html.Div(id="drip-output", children=html.Div([
            Styles.skeleton_kpis(4), Styles.skeleton_chart(),
        ])), type="dot"),
    ])


# ─────────────────────────────────────────────
# Callbacks
# ─────────────────────────────────────────────

def register_callbacks(app):
    @app.callback(
        Output("drip-output", "children"),
        [Input("drip-horizon", "value"),
         Input("drip-div-growth", "value"),
         Input("drip-price-growth", "value")]
    )
    def update_drip_simulation(horizon, div_growth, price_growth):
        horizon = horizon or 20
        div_growth_rate = (float(div_growth) / 100) if div_growth is not None else 0.05
        price_appreciation = (float(price_growth) / 100) if price_growth is not None else 0.07

        portfolio_value, dividend_yield = _get_portfolio_stats()

        if portfolio_value <= 0:
            return html.P("No portfolio data available. Ensure positions data is loaded.",
                          style={"color": "var(--text-muted)", "padding": "20px"})

        rows = _simulate_drip(portfolio_value, dividend_yield, div_growth_rate,
                              price_appreciation, horizon)

        if not rows:
            return html.P("Unable to run simulation.",
                          style={"color": "var(--text-muted)", "padding": "20px"})

        final = rows[-1]

        # ── KPIs ──
        kpis = html.Div([
            Styles.kpiboxes("Final Value (DRIP)",
                            f"{final['drip_value']:,.0f}",
                            Styles.colorPalette[0]),
            Styles.kpiboxes("Final Value (No DRIP)",
                            f"{final['no_drip_value']:,.0f}",
                            Styles.colorPalette[1]),
            Styles.kpiboxes("DRIP Advantage",
                            f"+{final['advantage_dollar']:,.0f} ({final['advantage_pct']:.1f}%)",
                            Styles.strongGreen),
            Styles.kpiboxes("Total Dividends Received",
                            f"{final['cumulative_dividends']:,.0f}",
                            Styles.colorPalette[3]),
        ], className="kpi-row")

        # ── Main chart: dual line with shaded gap ──
        years = [r["year"] for r in rows]
        drip_vals = [r["drip_value"] for r in rows]
        no_drip_vals = [r["no_drip_value"] for r in rows]

        chart = {
            'data': [
                {
                    'x': [0] + years,
                    'y': [portfolio_value] + drip_vals,
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': 'DRIP (Reinvest)',
                    'line': {'color': Styles.strongGreen, 'width': 3},
                    'fill': 'tonexty',
                    'fillcolor': 'rgba(52,199,89,0.10)',
                },
                {
                    'x': [0] + years,
                    'y': [portfolio_value] + no_drip_vals,
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': 'No DRIP (Cash)',
                    'line': {'color': Styles.colorPalette[1], 'width': 3},
                },
            ],
            'layout': Styles.graph_layout(
                title='Portfolio Value: DRIP vs No DRIP',
                xaxis={'title': 'Year', 'dtick': 5},
                yaxis={'title': 'Portfolio Value'},
                hovermode='x unified',
                legend={'orientation': 'h', 'y': -0.15, 'x': 0.5, 'xanchor': 'center'},
                margin={'b': 60},
            )
        }

        # Important: place the No-DRIP line first so DRIP can fill to it
        chart['data'] = [
            {
                'x': [0] + years,
                'y': [portfolio_value] + no_drip_vals,
                'type': 'scatter',
                'mode': 'lines',
                'name': 'No DRIP (Cash)',
                'line': {'color': Styles.colorPalette[1], 'width': 3},
            },
            {
                'x': [0] + years,
                'y': [portfolio_value] + drip_vals,
                'type': 'scatter',
                'mode': 'lines',
                'name': 'DRIP (Reinvest)',
                'line': {'color': Styles.strongGreen, 'width': 3},
                'fill': 'tonexty',
                'fillcolor': 'rgba(52,199,89,0.12)',
            },
        ]

        # ── Annual breakdown table ──
        table_data = []
        for r in rows:
            table_data.append({
                "Year": r["year"],
                "DRIP Value": f"{r['drip_value']:,.0f}",
                "No DRIP Value": f"{r['no_drip_value']:,.0f}",
                "Dividend Income": f"{r['dividend_income']:,.0f}",
                "Cum. Dividends": f"{r['cumulative_dividends']:,.0f}",
                "DRIP Adv. ($)": f"+{r['advantage_dollar']:,.0f}",
                "DRIP Adv. (%)": f"{r['advantage_pct']:.1f}%",
            })

        columns = [
            {"name": "Year", "id": "Year", "type": "numeric"},
            {"name": "DRIP Value", "id": "DRIP Value", "type": "text"},
            {"name": "No DRIP Value", "id": "No DRIP Value", "type": "text"},
            {"name": "Dividend Income", "id": "Dividend Income", "type": "text"},
            {"name": "Cum. Dividends", "id": "Cum. Dividends", "type": "text"},
            {"name": "DRIP Adv. ($)", "id": "DRIP Adv. ($)", "type": "text"},
            {"name": "DRIP Adv. (%)", "id": "DRIP Adv. (%)", "type": "text"},
        ]

        table = dash_table.DataTable(
            id="drip-breakdown-table",
            columns=columns,
            data=table_data,
            sort_action="native",
            page_size=30,
            fixed_rows={"headers": True},
            export_format="csv",
            export_headers="display",
            style_table={"overflowX": "auto", "overflowY": "auto", "maxHeight": "500px"},
            style_cell={"padding": "8px", "textAlign": "right", "fontSize": "13px"},
            style_header={
                "fontWeight": "bold",
                "fontSize": "13px",
                "fontFamily": Styles.GRAPH_LAYOUT["font"]["family"],
                "textAlign": "right",
            },
            style_data_conditional=[
                {"if": {"row_index": "odd"},
                 "backgroundColor": "var(--table-stripe, #f9f9f9)"},
            ],
            style_cell_conditional=[
                {"if": {"column_id": "Year"}, "textAlign": "center", "width": "60px"},
            ],
        )

        return html.Div([
            kpis,
            html.Div([dcc.Graph(id="drip-main-chart", figure=chart)], className="card"),
            html.H4("Annual Breakdown", style={"marginTop": "20px"}),
            html.Div([table], className="card", style={"marginBottom": "20px"}),
        ])
