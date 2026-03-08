from dash import dcc, html, Input, Output, State
import Styles
import dataLoadPositions as dlp
import dataLoadTransactions as dlt
import user_settings


def layout():
    saved = user_settings.get("networth", {})

    return html.Div([
        html.Hr(),
        html.H4("Net Worth Overview"),

        # --- Manual asset entry ---
        html.Div([
            html.Div([
                html.Label("Real Estate Value"),
                dcc.Input(id="nw-real-estate", type="number",
                          value=saved.get("real_estate", 0),
                          style={"width": "100%", "padding": "6px"}),
            ], style={"width": "18%", "display": "inline-block", "padding": "10px 15px"}),
            html.Div([
                html.Label("Cash & Savings"),
                dcc.Input(id="nw-cash", type="number",
                          value=saved.get("cash", 0),
                          style={"width": "100%", "padding": "6px"}),
            ], style={"width": "18%", "display": "inline-block", "padding": "10px 15px"}),
            html.Div([
                html.Label("Pension / 2nd Pillar"),
                dcc.Input(id="nw-pension", type="number",
                          value=saved.get("pension", 0),
                          style={"width": "100%", "padding": "6px"}),
            ], style={"width": "18%", "display": "inline-block", "padding": "10px 15px"}),
            html.Div([
                html.Label("Other Assets"),
                dcc.Input(id="nw-other", type="number",
                          value=saved.get("other", 0),
                          style={"width": "100%", "padding": "6px"}),
            ], style={"width": "18%", "display": "inline-block", "padding": "10px 15px"}),
            html.Div([
                html.Label("Liabilities (Debt)"),
                dcc.Input(id="nw-liabilities", type="number",
                          value=saved.get("liabilities", 0),
                          style={"width": "100%", "padding": "6px"}),
            ], style={"width": "18%", "display": "inline-block", "padding": "10px 15px"}),
        ], style={"marginBottom": "10px"}),

        # --- KPI row (dynamic) ---
        html.Div(id="nw-kpi-row"),
        html.Hr(),

        # --- Charts ---
        html.Div(id="nw-charts"),
    ])


def register_callbacks(app):
    @app.callback(
        [Output("nw-kpi-row", "children"),
         Output("nw-charts", "children")],
        [Input("nw-real-estate", "value"),
         Input("nw-cash", "value"),
         Input("nw-pension", "value"),
         Input("nw-other", "value"),
         Input("nw-liabilities", "value")]
    )
    def update_networth(real_estate, cash, pension, other, liabilities):
        real_estate = real_estate or 0
        cash = cash or 0
        pension = pension or 0
        other = other or 0
        liabilities = liabilities or 0

        # Persist values
        user_settings.save({"networth": {
            "real_estate": real_estate,
            "cash": cash,
            "pension": pension,
            "other": other,
            "liabilities": liabilities,
        }})

        portfolio_value = dlp.portfolio_total_value()
        total_assets = portfolio_value + real_estate + cash + pension + other
        net_worth = total_assets - liabilities

        # KPI boxes
        kpis = html.Div([
            Styles.kpiboxes("Portfolio:", f"{portfolio_value:,}", Styles.colorPalette[0]),
            Styles.kpiboxes("Total Assets:", f"{total_assets:,}", Styles.colorPalette[1]),
            Styles.kpiboxes("Liabilities:", f"{liabilities:,}", Styles.strongRed),
            Styles.kpiboxes("Net Worth:", f"{net_worth:,}", Styles.strongGreen),
        ])

        # Build asset breakdown for pie chart
        asset_labels = []
        asset_values = []

        df = dlp.fetch_data()
        if not df.empty:
            type_alloc = df.groupby("asset_type")["total_value"].sum()
            for atype, val in type_alloc.items():
                if val > 0:
                    asset_labels.append(f"Portfolio: {atype}")
                    asset_values.append(round(val, 2))

        if real_estate > 0:
            asset_labels.append("Real Estate")
            asset_values.append(real_estate)
        if cash > 0:
            asset_labels.append("Cash & Savings")
            asset_values.append(cash)
        if pension > 0:
            asset_labels.append("Pension")
            asset_values.append(pension)
        if other > 0:
            asset_labels.append("Other")
            asset_values.append(other)

        # Net Worth composition pie
        nw_pie = {
            'data': [{
                'type': 'pie',
                'labels': asset_labels,
                'values': asset_values,
                'textinfo': 'label+percent',
                'hoverinfo': 'label+value+percent',
                'marker': {'colors': Styles.purple_list + [Styles.strongGreen, Styles.strongRed]},
                'hole': 0.35,
            }],
            'layout': {
                'title': 'Net Worth Composition',
                'margin': {'t': 40, 'b': 40, 'l': 40, 'r': 40},
            }
        }

        # Assets vs Liabilities bar
        bar_labels = ["Portfolio", "Real Estate", "Cash", "Pension", "Other", "Liabilities"]
        bar_values = [portfolio_value, real_estate, cash, pension, other, -liabilities]
        bar_colors = [Styles.colorPalette[0], Styles.colorPalette[1],
                      Styles.colorPalette[2], Styles.colorPalette[3],
                      Styles.strongGreen, Styles.strongRed]

        bar_chart = {
            'data': [{
                'type': 'bar',
                'x': bar_labels,
                'y': bar_values,
                'marker': {'color': bar_colors},
                'text': [f"{v:,.0f}" for v in bar_values],
                'textposition': 'outside',
            }],
            'layout': {
                'title': 'Assets vs Liabilities',
                'yaxis': {'title': 'Value'},
                'margin': {'t': 40, 'b': 60, 'l': 60, 'r': 40},
            }
        }

        # Cumulative investment from Buy transactions (actual securities purchased)
        txn_df = dlt.ingest_transactions()
        inv_chart_div = html.Div()
        if not txn_df.empty and "date" in txn_df.columns and "net_amount" in txn_df.columns:
            buys = txn_df[txn_df["transaction"].str.lower().isin(
                ["buy", "crypto deposit"]
            )].copy()
            if not buys.empty:
                buys = buys.sort_values("date")
                buys["cumulative"] = buys["net_amount"].abs().cumsum()
                inv_chart = {
                    'data': [{
                        'x': buys["date"].dt.strftime("%Y-%m-%d").tolist(),
                        'y': buys["cumulative"].tolist(),
                        'type': 'scatter',
                        'mode': 'lines',
                        'fill': 'tozeroy',
                        'name': 'Cumulative Invested',
                        'line': {'color': Styles.colorPalette[0]},
                    }],
                    'layout': {
                        'title': 'Cumulative Capital Invested Over Time',
                        'xaxis': {'title': 'Date', 'type': 'date'},
                        'yaxis': {'title': 'Cumulative Amount'},
                        'margin': {'t': 40, 'b': 40, 'l': 60, 'r': 40},
                    }
                }
                inv_chart_div = html.Div([
                    dcc.Graph(id='nw-cumulative-investment', figure=inv_chart)
                ], style=Styles.STYLE(100))

        charts = html.Div([
            html.Div([
                dcc.Graph(id='nw-composition-pie', figure=nw_pie)
            ], style=Styles.STYLE(48)),
            html.Div([''], style=Styles.FILLER()),
            html.Div([
                dcc.Graph(id='nw-bar-chart', figure=bar_chart)
            ], style=Styles.STYLE(48)),
            html.Hr(),
            inv_chart_div,
        ])

        return kpis, charts
