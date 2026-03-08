import Styles
import dataLoadTransactions as dlt
import dataLoadPositions as dlp
from dash import dcc, html


def _build_dividend_analysis():
    """Build dividend income analysis section."""
    txn = dlt.ingest_transactions()
    if txn.empty or "transaction" not in txn.columns:
        return html.Div()

    dividends = txn[txn["transaction"].str.lower() == "dividend"].copy()
    if dividends.empty:
        return html.Div()

    # Dividend by symbol
    if "symbol" in dividends.columns and "net_amount" in dividends.columns:
        by_symbol = dividends.groupby("symbol")["net_amount"].sum().sort_values(ascending=True)

        div_by_symbol_chart = {
            'data': [{
                'type': 'bar',
                'x': by_symbol.values.round(2).tolist(),
                'y': by_symbol.index.tolist(),
                'orientation': 'h',
                'marker': {'color': Styles.strongGreen},
                'text': [f"{v:,.0f}" for v in by_symbol.values],
                'textposition': 'outside',
            }],
            'layout': Styles.graph_layout(
                title='Total Dividends Received by Holding',
                xaxis={'title': 'Total Dividends'},
                margin={'l': 120, 'r': 60},
                height=max(250, len(by_symbol) * 28),
            )
        }
    else:
        div_by_symbol_chart = {'data': [], 'layout': Styles.graph_layout(title='No symbol data')}

    # Monthly dividend trend (all years)
    div_trend_chart = {'data': [], 'layout': Styles.graph_layout(title='No date data')}
    if "date" in dividends.columns:
        dividends["year_month"] = dividends["date"].dt.to_period("M").astype(str)
        monthly = dividends.groupby("year_month")["net_amount"].sum().reset_index()

        div_trend_chart = {
            'data': [{
                'x': monthly["year_month"].tolist(),
                'y': monthly["net_amount"].round(2).tolist(),
                'type': 'bar',
                'marker': {'color': Styles.strongGreen},
                'name': 'Monthly Dividends',
            }],
            'layout': Styles.graph_layout(
                title='Monthly Dividend Income Over Time',
                xaxis={'title': 'Month'},
                yaxis={'title': 'Dividend Income'},
                margin={'b': 60, 'l': 60},
            )
        }

    # Dividend yield estimate
    positions = dlp.fetch_data()
    yield_section = html.Div()
    if not positions.empty and "symbol" in positions.columns and "total_value" in positions.columns:
        annual_divs = dividends[dividends["date"].dt.year == dlt.currentYear].groupby("symbol")["net_amount"].sum()
        if annual_divs.sum() == 0:
            annual_divs = dividends[dividends["date"].dt.year == dlt.currentYear - 1].groupby("symbol")["net_amount"].sum()

        pos_values = positions.set_index("symbol")["total_value"]
        yields = (annual_divs / pos_values).dropna()
        yields = yields[yields > 0].sort_values(ascending=True)

        if not yields.empty:
            yield_chart = {
                'data': [{
                    'type': 'bar',
                    'x': (yields * 100).round(2).tolist(),
                    'y': yields.index.tolist(),
                    'orientation': 'h',
                    'marker': {'color': Styles.colorPalette[2]},
                    'text': [f"{v:.2f}%" for v in (yields * 100)],
                    'textposition': 'outside',
                }],
                'layout': Styles.graph_layout(
                    title='Estimated Dividend Yield by Holding',
                    xaxis={'title': 'Yield (%)'},
                    margin={'l': 120, 'r': 60},
                    height=max(250, len(yields) * 28),
                )
            }
            yield_section = html.Div([
                dcc.Graph(id='dividend-yield-chart', figure=yield_chart)
            ], className="card", style=Styles.STYLE(48))

    return html.Div([
        html.Hr(),
        html.H4("Dividend Income Analysis"),
        html.Div([
            html.Div([
                dcc.Graph(id='div-trend-chart', figure=div_trend_chart)
            ], className="card", style=Styles.STYLE(100)),
        ]),
        html.Hr(),
        html.Div([
            html.Div([
                dcc.Graph(id='div-by-symbol-chart', figure=div_by_symbol_chart)
            ], className="card", style=Styles.STYLE(48)),
            html.Div([''], style=Styles.FILLER()),
            yield_section,
        ]),
    ])


def render_page_content():
    y2 = dlt.currentYear - 2
    y1 = dlt.currentYear - 1
    y0 = dlt.currentYear

    return html.Div([
        html.Hr(),
        html.Div([
            Styles.kpiboxes('Total Dividends',
                            dlt.total_transaction_amount(y0, "Dividend"),
                            Styles.colorPalette[0]),
            Styles.kpiboxes('Total New Investments',
                            dlt.total_transaction_amount(y0, "Payment"),
                            Styles.colorPalette[1]),
            Styles.kpiboxes('Total Sec. Lending',
                            dlt.total_transaction_amount(y0, "Securities Lending"),
                            Styles.colorPalette[2]),
            Styles.kpiboxes('Total Fees',
                            dlt.total_transaction_amount(y0, "Custody Fees"),
                            Styles.colorPalette[3]),
        ]),
        html.Hr(),
        html.Div([
            html.H4(f"Yearly Dividends"),
            dcc.Graph(
                id='yearly-dividend-overview-bar',
                figure={
                    'data': [
                        {
                            'x': dlt.yearly_transaction_summary()[0],
                            'y': dlt.yearly_transaction_summary()[1],
                            'type': 'bar',
                            'name': 'Yearly',
                            'marker': {'color': Styles.colorPalette[1]}
                        },
                    ],
                    'layout': Styles.graph_layout(
                        barmode='group',
                        title='Yearly Dividend Summary',
                        xaxis={'title': 'Year'},
                        yaxis={'title': 'Total'},
                    )
                }
            )
        ], className="card", style=Styles.STYLE(100)),
        html.Hr(),
        # --- Monthly Dividends: 3-year comparison ---
        html.Div([
            html.H4(f"Monthly Dividends: {y2} vs {y1} vs {y0}"),
            dcc.Graph(
                id='monthly-dividends-bar',
                figure={
                    'data': [
                        {
                            'x': dlt.months,
                            'y': dlt.monthly_totals("Dividend")[1],
                            'type': 'bar',
                            'name': str(y2),
                            'marker': {'color': Styles.colorPalette[2]}
                        },
                        {
                            'x': dlt.months,
                            'y': dlt.monthly_totals("Dividend")[2],
                            'type': 'bar',
                            'name': str(y1),
                            'marker': {'color': Styles.colorPalette[1]}
                        },
                        {
                            'x': dlt.months,
                            'y': dlt.monthly_totals("Dividend")[3],
                            'type': 'bar',
                            'name': str(y0),
                            'marker': {'color': Styles.colorPalette[0]}
                        },
                    ],
                    'layout': Styles.graph_layout(
                        barmode='group',
                        title='Monthly Dividends Comparison',
                        xaxis={'title': 'Month'},
                        yaxis={'title': 'Dividends Paid'},
                    )
                }
            )
        ], className="card", style=Styles.STYLE(80)),
        html.Div([''], style=Styles.FILLER()),
        html.Div([
            html.H4(f"Annual"),
            dcc.Graph(
                id='yearly-dividends-bar',
                figure={
                    'data': [
                        {
                            'x': [str(y2), str(y1), str(y0)],
                            'y': dlt.totals("Dividend"),
                            'type': 'bar',
                            'marker': {'color': [Styles.colorPalette[2],
                                                 Styles.colorPalette[1],
                                                 Styles.colorPalette[0]]},
                            'name': 'Yearly Dividend'
                        }
                    ],
                    'layout': Styles.graph_layout(
                        xaxis={'title': 'Year'},
                        yaxis={'title': 'Dividend Total'},
                    )
                }
            )
        ], className="card", style=Styles.STYLE(18)),
        # --------------------------------------------------------------------------------------------------------------
        html.Hr(),
        # --- Monthly Investments: 3-year comparison ---
        html.Div([
            html.H4(f"Monthly Investments: {y2} vs {y1} vs {y0}"),
            dcc.Graph(
                id='monthly-investment-comparison-bar',
                figure={
                    'data': [
                        {
                            'x': dlt.months,
                            'y': dlt.monthly_totals("Payment")[1],
                            'type': 'bar',
                            'name': str(y2),
                            'marker': {'color': Styles.colorPalette[2]}
                        },
                        {
                            'x': dlt.months,
                            'y': dlt.monthly_totals("Payment")[2],
                            'type': 'bar',
                            'name': str(y1),
                            'marker': {'color': Styles.colorPalette[1]}
                        },
                        {
                            'x': dlt.months,
                            'y': dlt.monthly_totals("Payment")[3],
                            'type': 'bar',
                            'name': str(y0),
                            'marker': {'color': Styles.colorPalette[0]}
                        },
                    ],
                    'layout': Styles.graph_layout(
                        barmode='group',
                        title='Monthly Investment Comparison',
                        xaxis={'title': 'Month'},
                        yaxis={'title': 'Investments'},
                    )
                }
            )
        ], className="card", style=Styles.STYLE(80)),
        html.Div([''], style=Styles.FILLER()),
        html.Div([
            html.H4(f"Annual"),
            dcc.Graph(
                id='yearly-investment-bar',
                figure={
                    'data': [
                        {
                            'x': [str(y2), str(y1), str(y0)],
                            'y': dlt.totals("Payment"),
                            'type': 'bar',
                            'marker': {'color': [Styles.colorPalette[2],
                                                 Styles.colorPalette[1],
                                                 Styles.colorPalette[0]]},
                            'name': 'Yearly Investments'
                        }
                    ],
                    'layout': Styles.graph_layout(
                        xaxis={'title': 'Year'},
                        yaxis={'title': 'Investment Total'},
                    )
                }
            )
        ], className="card", style=Styles.STYLE(18)),

        # Dividend analysis section
        _build_dividend_analysis(),
    ])
