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

def _get_dividends() -> pd.DataFrame:
    """Return a DataFrame of dividend transactions with positive amounts."""
    txn = dlt.ingest_transactions()
    if txn.empty or "transaction" not in txn.columns:
        return pd.DataFrame()

    dividends = txn[txn["transaction"].str.lower() == "dividend"].copy()
    if dividends.empty:
        return pd.DataFrame()

    if "net_amount" in dividends.columns:
        dividends["amount"] = dividends["net_amount"].abs()

    return dividends


# ─────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────

def _build_kpi_row(dividends):
    """5 KPIs with sparklines: Lifetime, YTD, Avg Monthly, Portfolio Yield, YoY Growth."""
    today = datetime.today()
    current_year = dlt.currentYear

    total_lifetime = dividends["amount"].sum()
    ytd = dividends[dividends["date"].dt.year == current_year]["amount"].sum()

    # Monthly average (across months that had dividends)
    monthly = dividends.groupby(dividends["date"].dt.to_period("M"))["amount"].sum()
    avg_monthly = monthly.mean() if len(monthly) > 0 else 0

    # YoY growth (last two complete years)
    yearly = dividends.groupby(dividends["date"].dt.year)["amount"].sum().sort_index()
    complete = yearly[yearly.index < current_year]
    if len(complete) >= 2 and complete.iloc[-2] > 0:
        yoy_growth = (complete.iloc[-1] - complete.iloc[-2]) / complete.iloc[-2] * 100
    else:
        yoy_growth = 0

    # Portfolio yield (TTM dividends / total market value)
    # Only include dividends from symbols that are currently held
    weighted_yield = 0
    positions = dlp.fetch_data()
    if not positions.empty and "total_value" in positions.columns:
        ttm_start = today - timedelta(days=365)
        current_symbols = set(positions["symbol"].unique())
        ttm_divs = dividends[
            (dividends["date"] >= ttm_start) & (dividends["symbol"].isin(current_symbols))
        ]
        ttm_total = ttm_divs["amount"].sum()
        portfolio_mv = positions["total_value"].sum()
        if portfolio_mv > 0:
            weighted_yield = ttm_total / portfolio_mv * 100

    # Sparkline: last 12 months of dividend income
    last_12 = dividends[dividends["date"] >= (today - timedelta(days=365))].copy()
    if not last_12.empty:
        spark = last_12.groupby(last_12["date"].dt.to_period("M"))["amount"].sum()
        spark_data = spark.values.tolist()
    else:
        spark_data = None

    return html.Div([
        Styles.kpiboxes_spark("Lifetime Dividends", f"{total_lifetime:,.0f}",
                              Styles.colorPalette[0], spark_data),
        Styles.kpiboxes_spark("YTD Dividends", f"{ytd:,.0f}",
                              Styles.colorPalette[1], spark_data),
        Styles.kpiboxes("Avg Monthly", f"{avg_monthly:,.0f}", Styles.colorPalette[2]),
        Styles.kpiboxes("Portfolio Yield", f"{weighted_yield:.2f}%", Styles.colorPalette[3]),
        Styles.kpiboxes("YoY Growth", f"{yoy_growth:+.1f}%",
                        Styles.strongGreen if yoy_growth >= 0 else Styles.strongRed),
    ], className="kpi-row")


def _build_timeline(dividends):
    """Full-width monthly dividend income bar chart (all time)."""
    df = dividends.copy()
    df["year_month"] = df["date"].dt.to_period("M").astype(str)
    monthly = df.groupby("year_month")["amount"].sum().reset_index()

    chart = {
        'data': [{
            'x': monthly["year_month"].tolist(),
            'y': monthly["amount"].round(2).tolist(),
            'type': 'bar',
            'marker': {'color': Styles.strongGreen},
        }],
        'layout': Styles.graph_layout(
            title='Monthly Dividend Income',
            yaxis={'title': 'Amount'},
            margin={'b': 40},
        )
    }

    return html.Div([
        dcc.Graph(id='div-monthly-timeline', figure=chart)
    ], className="card")


def _build_heatmap(dividends):
    """Month x year calendar heatmap."""
    df = dividends.copy()
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month

    pivot = df.pivot_table(
        values="amount", index="month", columns="year",
        aggfunc="sum", fill_value=0,
    )
    for m in range(1, 13):
        if m not in pivot.index:
            pivot.loc[m] = 0
    pivot = pivot.sort_index()

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    chart = {
        'data': [{
            'type': 'heatmap',
            'z': pivot.values.tolist(),
            'x': [str(c) for c in sorted(pivot.columns)],
            'y': month_labels,
            'text': [[f"{v:,.0f}" if v > 0 else "" for v in row] for row in pivot.values],
            'texttemplate': '%{text}',
            'hovertemplate': '%{y} %{x}: %{z:,.0f}<extra></extra>',
            'colorscale': [[0, 'rgba(0,0,0,0)'], [0.01, 'rgba(52,199,89,0.12)'], [1, '#34c759']],
            'showscale': False,
        }],
        'layout': Styles.graph_layout(
            title='Dividend Calendar',
            yaxis={'autorange': 'reversed'},
            margin={'l': 50, 'r': 20, 't': 40, 'b': 30},
            height=340,
        )
    }

    return html.Div([
        dcc.Graph(id='div-heatmap', figure=chart)
    ], className="card")


def _build_yoy_comparison():
    """3-year monthly comparison grouped bar chart."""
    y2 = dlt.currentYear - 2
    y1 = dlt.currentYear - 1
    y0 = dlt.currentYear
    _, vals_y2, vals_y1, vals_y0 = dlt.monthly_totals("Dividend")
    vals_y2 = [abs(v) for v in vals_y2]
    vals_y1 = [abs(v) for v in vals_y1]
    vals_y0 = [abs(v) for v in vals_y0]

    chart = {
        'data': [
            {'x': dlt.months, 'y': vals_y2, 'type': 'bar',
             'name': str(y2), 'marker': {'color': Styles.colorPalette[2]}},
            {'x': dlt.months, 'y': vals_y1, 'type': 'bar',
             'name': str(y1), 'marker': {'color': Styles.colorPalette[1]}},
            {'x': dlt.months, 'y': vals_y0, 'type': 'bar',
             'name': str(y0), 'marker': {'color': Styles.colorPalette[0]}},
        ],
        'layout': Styles.graph_layout(
            barmode='group',
            title='Year-over-Year Monthly Comparison',
            yaxis={'title': 'Dividends'},
        )
    }

    return html.Div([
        dcc.Graph(id='div-yoy-comparison', figure=chart)
    ], className="card")


def _build_annual_chart():
    """Annual dividend totals bar chart."""
    year_labels, year_values = dlt.yearly_transaction_summary()
    if not year_labels:
        return html.Div()

    chart = {
        'data': [{
            'x': year_labels,
            'y': [abs(v) for v in year_values],
            'type': 'bar',
            'marker': {'color': Styles.colorPalette[0]},
            'text': [f"{abs(v):,.0f}" for v in year_values],
            'textposition': 'outside',
        }],
        'layout': Styles.graph_layout(
            title='Annual Dividend Income',
            yaxis={'title': 'Total'},
        )
    }

    return html.Div([
        dcc.Graph(id='div-annual-chart', figure=chart)
    ], className="card")


def _build_by_symbol(dividends):
    """Total dividends by symbol — horizontal bar chart."""
    by_symbol = dividends.groupby("symbol")["amount"].sum().sort_values(ascending=True)

    chart = {
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
            title='Total Dividends by Holding',
            margin={'l': 100, 'r': 80},
            height=max(250, len(by_symbol) * 28),
        )
    }

    return html.Div([
        dcc.Graph(id='div-by-symbol', figure=chart)
    ], className="card")


def _build_yield_chart(dividends):
    """Trailing 12-month dividend yield by position."""
    positions = dlp.add_position_pnl_columns()
    if positions.empty or "symbol" not in positions.columns:
        return html.Div()

    today = datetime.today()
    twelve_months_ago = today - pd.DateOffset(months=12)
    ttm = dividends[dividends["date"] >= twelve_months_ago].copy()
    if ttm.empty:
        return html.Div()

    ttm_by_symbol = ttm.groupby("symbol")["amount"].sum()
    pos_mv = positions.set_index("symbol")["market_value"]
    yields = (ttm_by_symbol / pos_mv).dropna()
    yields = yields[yields > 0].sort_values(ascending=True)

    if yields.empty:
        return html.Div()

    chart = {
        'data': [{
            'type': 'bar',
            'x': (yields * 100).round(2).tolist(),
            'y': yields.index.tolist(),
            'orientation': 'h',
            'marker': {'color': Styles.colorPalette[1]},
            'text': [f"{v:.2f}%" for v in (yields * 100)],
            'textposition': 'outside',
        }],
        'layout': Styles.graph_layout(
            title='TTM Dividend Yield',
            xaxis={'title': 'Yield (%)'},
            margin={'l': 100, 'r': 80},
            height=max(280, len(yields) * 30),
        )
    }

    return html.Div([
        dcc.Graph(id='div-yield-chart', figure=chart)
    ], className="card")


def _build_upcoming_predictions(dividends):
    """Predict upcoming dividend months based on historical payment patterns."""
    today = datetime.today()
    current_month = today.month

    df = dividends.copy()
    df["month"] = df["date"].dt.month

    symbol_months = df.groupby("symbol")["month"].apply(set).to_dict()
    symbol_avg = df.groupby(["symbol", "month"])["amount"].mean().reset_index()

    month_names = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
                   7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

    predictions = []
    for symbol, hist_months in symbol_months.items():
        for m in sorted(hist_months):
            if m > current_month:
                avg_row = symbol_avg[
                    (symbol_avg["symbol"] == symbol) & (symbol_avg["month"] == m)
                ]
                est = avg_row["amount"].values[0] if len(avg_row) > 0 else 0
                predictions.append({
                    "symbol": symbol,
                    "month": month_names[m],
                    "estimated": round(est, 2),
                })

    if not predictions:
        return html.Div([
            html.P("No upcoming dividends predicted based on historical patterns.",
                   style={"fontStyle": "italic", "color": "var(--text-muted, #888)",
                          "padding": "12px 0"}),
        ])

    pred_df = pd.DataFrame(predictions).sort_values(["month", "symbol"])

    rows = []
    for _, row in pred_df.iterrows():
        rows.append(
            html.Tr([
                html.Td(row["symbol"], style={"padding": "6px 10px"}),
                html.Td(row["month"], style={"padding": "6px 10px"}),
                html.Td(f"{row['estimated']:,.2f}",
                         style={"padding": "6px 10px", "textAlign": "right",
                                "color": Styles.strongGreen, "fontWeight": "600"}),
            ])
        )

    return html.Div([
        html.Table([
            html.Thead(html.Tr([
                html.Th("Symbol", style={"padding": "8px 10px", "textAlign": "left",
                                          "borderBottom": "2px solid var(--border-color, #ddd)"}),
                html.Th("Expected Month", style={"padding": "8px 10px", "textAlign": "left",
                                                   "borderBottom": "2px solid var(--border-color, #ddd)"}),
                html.Th("Est. Amount", style={"padding": "8px 10px", "textAlign": "right",
                                                "borderBottom": "2px solid var(--border-color, #ddd)"}),
            ])),
            html.Tbody(rows),
        ], style={"width": "100%", "borderCollapse": "collapse", "fontSize": "14px"}),
    ], className="card")


def _build_yield_alerts(dividends):
    """Flag positions where TTM yield deviates > 20% from historical average."""
    positions = dlp.add_position_pnl_columns()
    if positions.empty or "symbol" not in positions.columns:
        return html.Div()

    today = datetime.today()
    twelve_months_ago = today - pd.DateOffset(months=12)
    pos_mv = positions.set_index("symbol")["market_value"]

    ttm = dividends[dividends["date"] >= twelve_months_ago].copy()
    if ttm.empty:
        return html.Div()
    ttm_by_sym = ttm.groupby("symbol")["amount"].sum()
    ttm_yield = (ttm_by_sym / pos_mv).dropna()

    df = dividends.copy()
    df["year"] = df["date"].dt.year
    yearly_by_sym = df.groupby(["symbol", "year"])["amount"].sum().reset_index()
    avg_annual_by_sym = yearly_by_sym.groupby("symbol")["amount"].mean()
    hist_yield = (avg_annual_by_sym / pos_mv).dropna()

    common = ttm_yield.index.intersection(hist_yield.index)
    if common.empty:
        return html.Div()

    alerts = []
    for sym in common:
        current = ttm_yield[sym]
        historical = hist_yield[sym]
        if historical == 0:
            continue
        deviation = (current - historical) / historical
        if abs(deviation) > 0.20:
            alerts.append({
                "symbol": sym,
                "ttm_yield": current,
                "hist_yield": historical,
                "deviation": deviation,
            })

    if not alerts:
        return html.Div([
            html.P("No significant yield deviations detected.",
                   style={"fontStyle": "italic", "color": "var(--text-muted, #888)",
                          "padding": "12px"}),
        ], className="card")

    alert_badges = []
    for a in sorted(alerts, key=lambda x: abs(x["deviation"]), reverse=True):
        is_up = a["deviation"] > 0
        color = Styles.strongGreen if is_up else Styles.strongRed
        direction = "UP" if is_up else "DOWN"
        alert_badges.append(
            html.Span(
                f"{a['symbol']}: {direction} {abs(a['deviation']):.0%} "
                f"(TTM {a['ttm_yield']:.2%} vs Hist {a['hist_yield']:.2%})",
                className="alert-badge",
                style={"backgroundColor": color},
            )
        )

    return html.Div([
        html.P("Positions where trailing yield deviates >20% from historical average.",
               style={"fontSize": "12px", "color": "var(--text-muted, #888)",
                      "margin": "0 0 8px 0"}),
        html.Div(alert_badges),
    ], className="card")


def _build_symbol_table(dividends):
    """Per-symbol summary DataTable with CSV export."""
    by_sym = dividends.groupby("symbol").agg(
        total_dividends=("amount", "sum"),
        payment_count=("amount", "count"),
        last_payment=("date", "max"),
    ).reset_index()

    by_sym["avg_per_payment"] = (
        by_sym["total_dividends"] / by_sym["payment_count"]
    ).round(2)
    by_sym["total_dividends"] = by_sym["total_dividends"].round(2)
    by_sym["last_payment"] = by_sym["last_payment"].dt.strftime("%Y-%m-%d")
    by_sym = by_sym.sort_values("total_dividends", ascending=False).reset_index(drop=True)

    columns = [
        {"name": "Symbol", "id": "symbol", "type": "text"},
        {"name": "Total Dividends", "id": "total_dividends", "type": "numeric"},
        {"name": "Payments", "id": "payment_count", "type": "numeric"},
        {"name": "Last Payment", "id": "last_payment", "type": "text"},
        {"name": "Avg / Payment", "id": "avg_per_payment", "type": "numeric"},
    ]

    return html.Div([
        dash_table.DataTable(
            id="dividend-symbol-table",
            columns=columns,
            data=by_sym.to_dict("records"),
            sort_action="native",
            filter_action="native",
            page_size=20,
            fixed_rows={"headers": True},
            export_format="csv",
            export_headers="display",
            style_table={"overflowX": "auto", "overflowY": "auto", "maxHeight": "500px"},
            style_cell={"padding": "8px", "textAlign": "left", "fontSize": "13px"},
            style_header={
                "fontWeight": "bold",
                "fontSize": "13px",
                "fontFamily": Styles.GRAPH_LAYOUT["font"]["family"],
            },
            style_data_conditional=[
                {"if": {"row_index": "odd"},
                 "backgroundColor": "var(--table-stripe, #f9f9f9)"},
            ],
        ),
    ], className="card", style={"marginBottom": "20px"})


# ─────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────

def layout():
    dividends = _get_dividends()

    if dividends.empty:
        return html.Div([
            html.H4("Dividends"),
            html.P("No dividend data available.",
                   style={"fontStyle": "italic", "color": "var(--text-muted, #888)",
                          "padding": "20px"}),
        ])

    return html.Div([
        html.H4("Dividends"),

        # ── KPIs ──
        _build_kpi_row(dividends),

        # ── Monthly income timeline (full width) ──
        _build_timeline(dividends),

        # ── Heatmap + YoY comparison ──
        html.Div([
            _build_heatmap(dividends),
            _build_yoy_comparison(),
        ], className="grid-2"),

        # ── Annual totals + By symbol ──
        html.Div([
            _build_annual_chart(),
            _build_by_symbol(dividends),
        ], className="grid-2"),

        # ── Yield chart + Yield alerts ──
        html.Div([
            _build_yield_chart(dividends),
            _build_yield_alerts(dividends),
        ], className="grid-2"),

        # ── Upcoming predictions ──
        html.H4("Upcoming Predictions"),
        html.P("Based on historical payment months and average amounts.",
               style={"fontSize": "13px", "color": "var(--text-muted, #888)",
                      "margin": "0 0 8px 0"}),
        _build_upcoming_predictions(dividends),

        # ── Dividend Projection (interactive) ──
        html.H4("Dividend Projection"),
        html.P("Project future dividend income based on historical growth trends.",
               style={"fontSize": "13px", "color": "var(--text-muted, #888)",
                      "margin": "0 0 12px 0"}),
        html.Div([
            html.Div([
                html.Label("Projection Horizon (years)"),
                dcc.Slider(
                    id="proj-horizon",
                    min=5, max=30, step=5, value=10,
                    marks={5: "5", 10: "10", 15: "15", 20: "20", 25: "25", 30: "30"},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ], style={"flex": "1", "padding": "10px 20px"}),
            html.Div([
                html.Label("Growth Rate (% p.a.)"),
                dcc.Input(
                    id="proj-growth-override",
                    type="number", value=5.5, step=0.5, min=0, max=20,
                    style={"width": "100px", "padding": "6px 10px",
                           "borderRadius": "8px",
                           "border": "1px solid var(--border-color, #ddd)"},
                ),
            ], style={"flex": "1", "padding": "10px 20px"}),
        ], style={"display": "flex", "flexWrap": "wrap", "marginBottom": "16px"}),

        dcc.Loading(html.Div(id="div-projection-output", children=html.Div([
            Styles.skeleton_kpis(4), Styles.skeleton_chart(),
        ])), type="dot"),

        # ── Per-symbol summary table ──
        html.H4("Per-Symbol Summary"),
        _build_symbol_table(dividends),
    ])


# ─────────────────────────────────────────────
# Callbacks
# ─────────────────────────────────────────────

def register_callbacks(app):
    @app.callback(
        Output("div-projection-output", "children"),
        [Input("proj-horizon", "value"),
         Input("proj-growth-override", "value")]
    )
    def update_dividend_projection(horizon, growth_override):
        horizon = horizon or 10

        # Gather historical annual dividends
        year_labels, year_values = dlt.yearly_transaction_summary()
        if not year_labels:
            return html.P("No historical dividend data available.",
                          style={"color": "var(--text-muted)", "padding": "20px"})

        hist_years = [int(y) for y in year_labels]
        hist_values = [abs(v) for v in year_values]

        # Growth rate
        market_growth = 0.055
        if growth_override is not None and growth_override != "":
            market_growth = float(growth_override) / 100

        # Base: last complete year
        current_year = dlt.currentYear
        if hist_years[-1] == current_year and len(hist_years) >= 2:
            base_year = hist_years[-2]
            base_val = hist_values[-2]
        else:
            base_year = hist_years[-1]
            base_val = hist_values[-1]

        # Project yearly dividends
        proj_years = list(range(base_year + 1, base_year + horizon + 1))
        proj_values = [base_val * (1 + market_growth) ** i for i in range(1, horizon + 1)]
        cum_values = list(np.cumsum(proj_values))

        # KPIs
        years_to_double = round(72 / (market_growth * 100), 1) if market_growth > 0 else float('inf')
        ytd_str = f"{years_to_double:.1f}y" if years_to_double < 100 else "N/A"

        kpis = html.Div([
            Styles.kpiboxes("Growth Rate", f"{market_growth:.1%}", Styles.colorPalette[0]),
            Styles.kpiboxes(f"Yr {horizon} Annual Div.",
                            f"{proj_values[-1]:,.0f}", Styles.colorPalette[1]),
            Styles.kpiboxes(f"Cumulative ({horizon}y)",
                            f"{cum_values[-1]:,.0f}", Styles.colorPalette[2]),
            Styles.kpiboxes("Years to Double", ytd_str, Styles.colorPalette[3]),
        ], className="kpi-row")

        # Chart: historical + projected bars
        chart = {
            'data': [
                {
                    'x': [str(y) for y in hist_years],
                    'y': hist_values,
                    'type': 'bar',
                    'name': 'Historical',
                    'marker': {'color': Styles.strongGreen},
                },
                {
                    'x': [str(y) for y in proj_years],
                    'y': [round(v, 2) for v in proj_values],
                    'type': 'bar',
                    'name': f'Projected ({market_growth:.1%} p.a.)',
                    'marker': {'color': Styles.colorPalette[0], 'opacity': 0.6},
                },
            ],
            'layout': Styles.graph_layout(
                title='Yearly Dividends \u2014 Historical & Projected',
                xaxis={'title': 'Year'},
                yaxis={'title': 'Annual Dividends'},
                hovermode='x unified',
                legend={'orientation': 'h', 'y': -0.15, 'x': 0.5, 'xanchor': 'center'},
                margin={'b': 60},
            )
        }

        # Cumulative chart
        cum_chart = {
            'data': [{
                'x': [str(y) for y in proj_years],
                'y': [round(v, 2) for v in cum_values],
                'type': 'scatter',
                'mode': 'lines+markers',
                'name': 'Cumulative Dividends',
                'line': {'color': Styles.strongGreen, 'width': 3},
                'marker': {'size': 5},
                'fill': 'tozeroy',
                'fillcolor': 'rgba(52,199,89,0.1)',
            }],
            'layout': Styles.graph_layout(
                title='Cumulative Projected Dividends',
                xaxis={'title': 'Year'},
                yaxis={'title': 'Cumulative Total'},
                margin={'b': 50},
            )
        }

        return html.Div([
            kpis,
            html.Div([
                html.Div([dcc.Graph(figure=chart)], className="card"),
                html.Div([dcc.Graph(figure=cum_chart)], className="card"),
            ], className="grid-2"),
        ])
