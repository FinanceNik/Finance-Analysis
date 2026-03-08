import pandas as pd
from datetime import datetime
from dash import dcc, html, dash_table
import plotly.graph_objects as go
import Styles
import dataLoadTransactions as dlt
import dataLoadPositions as dlp


def _get_dividends() -> pd.DataFrame:
    """Return a DataFrame of dividend transactions with positive amounts."""
    txn = dlt.ingest_transactions()
    if txn.empty or "transaction" not in txn.columns:
        return pd.DataFrame()

    dividends = txn[txn["transaction"].str.lower() == "dividend"].copy()
    if dividends.empty:
        return pd.DataFrame()

    # Ensure positive amounts regardless of sign convention
    if "net_amount" in dividends.columns:
        dividends["amount"] = dividends["net_amount"].abs()

    return dividends


def _build_kpi_row(dividends: pd.DataFrame):
    """Build the KPI row: lifetime total, YTD, avg per payment, count."""
    total_lifetime = dividends["amount"].sum()
    total_count = len(dividends)
    avg_per_payment = total_lifetime / total_count if total_count > 0 else 0

    current_year = dlt.currentYear
    ytd = dividends[dividends["date"].dt.year == current_year]["amount"].sum()

    return html.Div([
        Styles.kpiboxes("Total Lifetime Dividends",
                        f"{total_lifetime:,.2f}",
                        Styles.colorPalette[0]),
        Styles.kpiboxes("YTD Dividends",
                        f"{ytd:,.2f}",
                        Styles.colorPalette[1]),
        Styles.kpiboxes("Avg per Payment",
                        f"{avg_per_payment:,.2f}",
                        Styles.colorPalette[2]),
        Styles.kpiboxes("Total Payments",
                        f"{total_count}",
                        Styles.colorPalette[3]),
    ])


def _build_heatmap(dividends: pd.DataFrame):
    """Build month x year heatmap of dividend amounts."""
    df = dividends.copy()
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month

    pivot = df.pivot_table(
        values="amount", index="month", columns="year",
        aggfunc="sum", fill_value=0,
    )
    # Ensure all months 1-12 are present
    for m in range(1, 13):
        if m not in pivot.index:
            pivot.loc[m] = 0
    pivot = pivot.sort_index()

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    year_labels = [str(y) for y in sorted(pivot.columns)]
    z_values = pivot.values.tolist()

    # Build text annotations
    text_values = [[f"{v:,.0f}" if v > 0 else "" for v in row] for row in z_values]

    fig = go.Figure(data=go.Heatmap(
        z=z_values,
        x=year_labels,
        y=month_labels,
        text=text_values,
        texttemplate="%{text}",
        colorscale=[[0, "#f0f0f0"], [1, "#34c759"]],
        showscale=True,
        hovertemplate="Year: %{x}<br>Month: %{y}<br>Amount: %{z:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        **Styles.graph_layout(
            title="Dividend Heatmap (Month x Year)",
            xaxis={"title": "Year"},
            yaxis={"title": "Month", "autorange": "reversed"},
            margin={"t": 50, "b": 50, "l": 70, "r": 30},
        ),
        height=420,
    )

    return html.Div([
        dcc.Graph(id="dividend-heatmap", figure=fig)
    ], className="card", style=Styles.STYLE(100))


def _build_symbol_table(dividends: pd.DataFrame):
    """Build a per-symbol summary DataTable."""
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
        {"name": "Payment Count", "id": "payment_count", "type": "numeric"},
        {"name": "Last Payment", "id": "last_payment", "type": "text"},
        {"name": "Avg per Payment", "id": "avg_per_payment", "type": "numeric"},
    ]

    return html.Div([
        html.H4("Per-Symbol Dividend Summary"),
        dash_table.DataTable(
            id="dividend-symbol-table",
            columns=columns,
            data=by_sym.to_dict("records"),
            sort_action="native",
            filter_action="native",
            page_size=20,
            style_table={"overflowX": "auto"},
            style_cell={"padding": "8px", "textAlign": "left", "fontSize": "14px"},
            style_header={
                "backgroundColor": Styles.colorPalette[0],
                "color": "white",
                "fontWeight": "bold",
                "fontSize": "14px",
                "fontFamily": Styles.GRAPH_LAYOUT["font"]["family"],
            },
            style_data_conditional=[
                {"if": {"row_index": "odd"}, "backgroundColor": "#f9f9f9"},
            ],
        ),
    ], className="card", style={**Styles.STYLE(100), "marginBottom": "20px"})


def _build_yield_chart(dividends: pd.DataFrame):
    """Build horizontal bar chart of trailing 12-month dividend yield by position."""
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
        "data": [{
            "type": "bar",
            "x": (yields * 100).round(2).tolist(),
            "y": yields.index.tolist(),
            "orientation": "h",
            "marker": {"color": Styles.strongGreen},
            "text": [f"{v:.2f}%" for v in (yields * 100)],
            "textposition": "outside",
        }],
        "layout": {
            **Styles.graph_layout(
                title="Trailing 12-Month Dividend Yield by Position",
                xaxis={"title": "Yield (%)"},
                margin={"l": 120, "r": 60},
            ),
            "height": max(280, len(yields) * 30),
        },
    }

    return html.Div([
        dcc.Graph(id="dividend-yield-bar", figure=chart)
    ], className="card", style=Styles.STYLE(48))


def _build_upcoming_predictions(dividends: pd.DataFrame):
    """Predict upcoming dividend months based on historical patterns."""
    today = datetime.today()
    current_month = today.month
    current_year = today.year

    # For each symbol, find which months historically had dividends
    df = dividends.copy()
    df["month"] = df["date"].dt.month

    symbol_months = df.groupby("symbol")["month"].apply(set).to_dict()
    symbol_avg = df.groupby(["symbol", "month"])["amount"].mean().reset_index()

    month_names = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
                   7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}

    predictions = []
    for symbol, hist_months in symbol_months.items():
        for m in sorted(hist_months):
            if m > current_month or (m <= current_month and current_year < dlt.currentYear):
                # Only future months in the current year
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
            html.H4("Upcoming Dividend Predictions"),
            html.P("No upcoming dividends predicted based on historical patterns.",
                    style={"fontStyle": "italic", "color": "#888"}),
        ], className="card", style=Styles.STYLE(48))

    pred_df = pd.DataFrame(predictions).sort_values(["month", "symbol"])

    rows = []
    for _, row in pred_df.iterrows():
        rows.append(
            html.Tr([
                html.Td(row["symbol"], style={"padding": "4px 8px"}),
                html.Td(row["month"], style={"padding": "4px 8px"}),
                html.Td(f"{row['estimated']:,.2f}",
                         style={"padding": "4px 8px", "textAlign": "right"}),
            ])
        )

    return html.Div([
        html.H4("Upcoming Dividend Predictions"),
        html.P("Based on historical payment months and average amounts.",
                style={"fontSize": "12px", "color": "#888", "marginBottom": "8px"}),
        html.Table([
            html.Thead(html.Tr([
                html.Th("Symbol", style={"padding": "6px 8px", "textAlign": "left",
                                          "borderBottom": "2px solid #ddd"}),
                html.Th("Month", style={"padding": "6px 8px", "textAlign": "left",
                                          "borderBottom": "2px solid #ddd"}),
                html.Th("Est. Amount", style={"padding": "6px 8px", "textAlign": "right",
                                                "borderBottom": "2px solid #ddd"}),
            ])),
            html.Tbody(rows),
        ], style={"width": "100%", "borderCollapse": "collapse", "fontSize": "14px"}),
    ], className="card", style=Styles.STYLE(48))


def _build_yield_alerts(dividends: pd.DataFrame):
    """Compare current TTM yield vs historical average yield per symbol.
    Flag positions where deviation > 20%.
    """
    positions = dlp.add_position_pnl_columns()
    if positions.empty or "symbol" not in positions.columns:
        return html.Div()

    today = datetime.today()
    twelve_months_ago = today - pd.DateOffset(months=12)
    pos_mv = positions.set_index("symbol")["market_value"]

    # TTM yield
    ttm = dividends[dividends["date"] >= twelve_months_ago].copy()
    if ttm.empty:
        return html.Div()
    ttm_by_sym = ttm.groupby("symbol")["amount"].sum()
    ttm_yield = (ttm_by_sym / pos_mv).dropna()

    # Historical average annual yield
    df = dividends.copy()
    df["year"] = df["date"].dt.year
    yearly_by_sym = df.groupby(["symbol", "year"])["amount"].sum().reset_index()
    avg_annual_by_sym = yearly_by_sym.groupby("symbol")["amount"].mean()
    hist_yield = (avg_annual_by_sym / pos_mv).dropna()

    # Find symbols in both
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
            html.H4("Yield Alerts"),
            html.P("No significant yield deviations detected (threshold: 20%).",
                    style={"fontStyle": "italic", "color": "#888"}),
        ], className="card", style={**Styles.STYLE(100), "marginBottom": "10px"})

    alert_badges = []
    for a in sorted(alerts, key=lambda x: abs(x["deviation"]), reverse=True):
        is_up = a["deviation"] > 0
        color = Styles.strongGreen if is_up else Styles.strongRed
        direction = "UP" if is_up else "DOWN"
        badge_style = {
            "display": "inline-block",
            "padding": "6px 14px",
            "margin": "4px 6px",
            "borderRadius": "8px",
            "backgroundColor": color,
            "color": "white",
            "fontSize": "13px",
            "fontWeight": "bold",
        }
        alert_badges.append(
            html.Span(
                f"{a['symbol']}: {direction} {abs(a['deviation']):.0%} "
                f"(TTM {a['ttm_yield']:.2%} vs Hist {a['hist_yield']:.2%})",
                style=badge_style,
            )
        )

    return html.Div([
        html.H4("Yield Alerts"),
        html.P("Positions where trailing 12-month yield deviates >20% from historical average.",
                style={"fontSize": "12px", "color": "#888", "marginBottom": "8px"}),
        html.Div(alert_badges),
    ], className="card", style={**Styles.STYLE(100), "marginBottom": "10px"})


def layout():
    dividends = _get_dividends()

    if dividends.empty:
        return html.Div([
            html.Hr(),
            html.H4("Dividend Calendar & Yield Analysis"),
            html.P("No dividend data available.",
                    style={"fontStyle": "italic", "color": "#888", "padding": "20px"}),
        ])

    return html.Div([
        html.Hr(),
        html.H4("Dividend Calendar & Yield Analysis"),

        # KPIs
        _build_kpi_row(dividends),
        html.Hr(),

        # Heatmap (100%)
        _build_heatmap(dividends),
        html.Hr(),

        # Yield chart (48%) + Upcoming predictions (48%)
        html.Div([
            _build_yield_chart(dividends),
            html.Div([""], style=Styles.FILLER()),
            _build_upcoming_predictions(dividends),
        ]),
        html.Hr(),

        # Yield alerts
        _build_yield_alerts(dividends),
        html.Hr(),

        # Symbol table (100%)
        _build_symbol_table(dividends),
    ])
