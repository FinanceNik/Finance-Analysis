import numpy as np
import Styles
import dataLoadTransactions as dlt
import dataLoadPositions as dlp
from dash import dcc, html, Input, Output


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

        # ── Dividend Projection Section ──
        html.Hr(),
        html.H4("Dividend Projection"),
        html.Div([
            html.Div([
                html.Label("Projection Horizon (years)"),
                dcc.Slider(
                    id="proj-horizon",
                    min=5, max=20, step=5, value=10,
                    marks={5: "5", 10: "10", 15: "15", 20: "20"},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ], style={"width": "45%", "display": "inline-block", "padding": "10px 20px",
                       "verticalAlign": "top"}),
            html.Div([
                html.Label("Growth Rate Override (% p.a.) — leave empty for auto"),
                dcc.Input(
                    id="proj-growth-override",
                    type="number",
                    placeholder="Auto (CAGR)",
                    step=0.5,
                    style={"width": "160px", "padding": "6px 10px",
                           "borderRadius": "8px", "border": "1px solid var(--border-color, #ddd)"},
                ),
            ], style={"width": "45%", "display": "inline-block", "padding": "10px 20px",
                       "verticalAlign": "top"}),
        ]),
        html.Div(id="div-projection-output"),
    ])


def register_callbacks(app):
    @app.callback(
        Output("div-projection-output", "children"),
        [Input("proj-horizon", "value"),
         Input("proj-growth-override", "value")]
    )
    def update_dividend_projection(horizon, growth_override):
        horizon = horizon or 10

        # ── Gather historical annual dividends ──
        year_labels, year_values = dlt.yearly_transaction_summary()
        if len(year_labels) < 2:
            return html.P("Not enough historical dividend data to project.",
                          style={"color": "var(--text-muted)", "padding": "20px"})

        hist_years = [int(y) for y in year_labels]
        hist_values = [abs(v) for v in year_values]  # dividends may be negative in data

        # ── Calculate CAGR from last 3 years (or all available) ──
        n_hist = min(3, len(hist_values))
        recent_years = hist_years[-n_hist:]
        recent_vals = hist_values[-n_hist:]

        # Use first and last of the recent window for CAGR
        start_val = recent_vals[0]
        end_val = recent_vals[-1]
        n_periods = recent_years[-1] - recent_years[0]

        if start_val > 0 and n_periods > 0:
            cagr = (end_val / start_val) ** (1 / n_periods) - 1
        else:
            cagr = 0.0

        # Apply override if provided
        if growth_override is not None and growth_override != "":
            base_growth = float(growth_override) / 100
        else:
            base_growth = cagr

        # ── Scenarios ──
        optimistic_rate = base_growth + 0.02
        conservative_rate = max(base_growth - 0.02, 0.0)

        base_year = hist_years[-1]
        base_val = hist_values[-1]

        proj_years = list(range(base_year + 1, base_year + horizon + 1))

        def project(rate):
            return [base_val * (1 + rate) ** i for i in range(1, horizon + 1)]

        proj_base = project(base_growth)
        proj_opt = project(optimistic_rate)
        proj_cons = project(conservative_rate)

        # Cumulative sums
        cum_base = list(np.cumsum(proj_base))
        cum_opt = list(np.cumsum(proj_opt))
        cum_cons = list(np.cumsum(proj_cons))

        # ── KPIs ──
        years_to_double = round(72 / (base_growth * 100), 1) if base_growth > 0 else float('inf')
        ytd_str = f"{years_to_double:.1f}" if years_to_double < 100 else "N/A"

        kpis = html.Div([
            Styles.kpiboxes("Historical CAGR", f"{cagr:.1%}", Styles.colorPalette[0]),
            Styles.kpiboxes("Projected Annual (Yr {})".format(horizon),
                            f"{proj_base[-1]:,.0f}", Styles.colorPalette[1]),
            Styles.kpiboxes("Cumulative Total",
                            f"{cum_base[-1]:,.0f}", Styles.colorPalette[2]),
            Styles.kpiboxes("Years to Double", ytd_str, Styles.colorPalette[3]),
        ])

        # ── Chart 1: Annual projection with historical bars + projected lines ──
        annual_chart = {
            'data': [
                # Historical bars
                {
                    'x': [str(y) for y in hist_years],
                    'y': hist_values,
                    'type': 'bar',
                    'name': 'Historical',
                    'marker': {'color': Styles.strongGreen, 'opacity': 0.7},
                },
                # Shaded band: conservative to optimistic
                {
                    'x': [str(y) for y in proj_years] + [str(y) for y in reversed(proj_years)],
                    'y': proj_opt + list(reversed(proj_cons)),
                    'type': 'scatter',
                    'fill': 'toself',
                    'fillcolor': 'rgba(55,63,81,0.12)',
                    'line': {'color': 'rgba(0,0,0,0)'},
                    'name': 'Range',
                    'showlegend': True,
                    'hoverinfo': 'skip',
                },
                # Conservative line
                {
                    'x': [str(y) for y in proj_years],
                    'y': proj_cons,
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': f'Conservative ({conservative_rate:.1%})',
                    'line': {'color': Styles.strongRed, 'width': 1, 'dash': 'dot'},
                },
                # Base line
                {
                    'x': [str(y) for y in proj_years],
                    'y': proj_base,
                    'type': 'scatter',
                    'mode': 'lines+markers',
                    'name': f'Base ({base_growth:.1%})',
                    'line': {'color': Styles.colorPalette[0], 'width': 3},
                    'marker': {'size': 6},
                },
                # Optimistic line
                {
                    'x': [str(y) for y in proj_years],
                    'y': proj_opt,
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': f'Optimistic ({optimistic_rate:.1%})',
                    'line': {'color': Styles.strongGreen, 'width': 1, 'dash': 'dot'},
                },
            ],
            'layout': Styles.graph_layout(
                title='Annual Dividend Projection',
                xaxis={'title': 'Year'},
                yaxis={'title': 'Annual Dividends'},
                hovermode='x unified',
                legend={'orientation': 'h', 'y': -0.18, 'x': 0.5, 'xanchor': 'center'},
                margin={'b': 70},
            )
        }

        # ── Chart 2: Cumulative dividends ──
        cum_chart = {
            'data': [
                # Shaded band
                {
                    'x': [str(y) for y in proj_years] + [str(y) for y in reversed(proj_years)],
                    'y': cum_opt + list(reversed(cum_cons)),
                    'type': 'scatter',
                    'fill': 'toself',
                    'fillcolor': 'rgba(52,199,89,0.12)',
                    'line': {'color': 'rgba(0,0,0,0)'},
                    'name': 'Range',
                    'hoverinfo': 'skip',
                },
                {
                    'x': [str(y) for y in proj_years],
                    'y': cum_cons,
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': 'Conservative',
                    'line': {'color': Styles.strongRed, 'width': 1, 'dash': 'dot'},
                },
                {
                    'x': [str(y) for y in proj_years],
                    'y': cum_base,
                    'type': 'scatter',
                    'mode': 'lines+markers',
                    'name': 'Base',
                    'line': {'color': Styles.strongGreen, 'width': 3},
                    'marker': {'size': 6},
                },
                {
                    'x': [str(y) for y in proj_years],
                    'y': cum_opt,
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': 'Optimistic',
                    'line': {'color': Styles.colorPalette[0], 'width': 1, 'dash': 'dot'},
                },
            ],
            'layout': Styles.graph_layout(
                title='Cumulative Projected Dividends',
                xaxis={'title': 'Year'},
                yaxis={'title': 'Cumulative Dividends'},
                hovermode='x unified',
                legend={'orientation': 'h', 'y': -0.18, 'x': 0.5, 'xanchor': 'center'},
                margin={'b': 70},
            )
        }

        # ── Per-symbol growth table ──
        symbol_section = _build_symbol_projection()

        return html.Div([
            kpis,
            html.Hr(),
            html.Div([
                dcc.Graph(figure=annual_chart),
            ], className="card", style=Styles.STYLE(48)),
            html.Div([''], style=Styles.FILLER()),
            html.Div([
                dcc.Graph(figure=cum_chart),
            ], className="card", style=Styles.STYLE(48)),
            html.Hr(),
            symbol_section,
        ])


def _build_symbol_projection():
    """Build a per-symbol dividend growth summary table."""
    txn = dlt.ingest_transactions()
    if txn.empty or "transaction" not in txn.columns:
        return html.Div()

    dividends = txn[txn["transaction"].str.lower() == "dividend"].copy()
    if dividends.empty or "symbol" not in dividends.columns or "date" not in dividends.columns:
        return html.Div()

    dividends["year"] = dividends["date"].dt.year
    dividends["net_amount"] = dividends["net_amount"].abs()

    # Annual dividends per symbol
    annual = dividends.groupby(["symbol", "year"])["net_amount"].sum().reset_index()

    symbols = annual["symbol"].unique()
    rows = []
    for sym in sorted(symbols):
        sym_data = annual[annual["symbol"] == sym].sort_values("year")
        if len(sym_data) < 2:
            continue
        years = sym_data["year"].tolist()
        vals = sym_data["net_amount"].tolist()

        # CAGR over available data (up to 3 recent years)
        n = min(3, len(vals))
        start_v, end_v = vals[-n], vals[-1]
        n_periods = years[-1] - years[-n]
        if start_v > 0 and n_periods > 0:
            sym_cagr = (end_v / start_v) ** (1 / n_periods) - 1
        else:
            sym_cagr = 0.0

        rows.append({
            "symbol": sym,
            "latest": f"{vals[-1]:,.0f}",
            "cagr": f"{sym_cagr:.1%}",
            "proj_5y": f"{vals[-1] * (1 + sym_cagr) ** 5:,.0f}",
            "proj_10y": f"{vals[-1] * (1 + sym_cagr) ** 10:,.0f}",
        })

    if not rows:
        return html.Div()

    header = html.Tr([
        html.Th("Symbol"), html.Th("Latest Annual"),
        html.Th("CAGR"), html.Th("Proj. 5Y"), html.Th("Proj. 10Y"),
    ])
    body = [
        html.Tr([
            html.Td(r["symbol"]), html.Td(r["latest"]),
            html.Td(r["cagr"]), html.Td(r["proj_5y"]), html.Td(r["proj_10y"]),
        ]) for r in rows
    ]

    table_style = {
        "width": "100%", "borderCollapse": "collapse",
        "fontSize": "14px",
    }
    th_style = {
        "padding": "10px 12px", "textAlign": "left",
        "borderBottom": "2px solid var(--border-color, #ddd)",
        "fontWeight": "600",
    }
    td_style = {
        "padding": "8px 12px", "textAlign": "left",
        "borderBottom": "1px solid var(--border-color, #eee)",
    }

    # Apply styles inline
    styled_header = html.Tr([
        html.Th(c.children, style=th_style) for c in header.children
    ])
    styled_body = [
        html.Tr([
            html.Td(cell.children, style=td_style) for cell in row.children
        ]) for row in body
    ]

    return html.Div([
        html.H4("Per-Symbol Dividend Growth"),
        html.Table(
            [html.Thead(styled_header), html.Tbody(styled_body)],
            style=table_style,
        ),
    ], className="card", style={**Styles.STYLE(100), "marginBottom": "20px"})
