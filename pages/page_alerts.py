import json
import time
import Styles
from dash import dcc, html, Input, Output, State, dash_table, callback_context
import yfinance as yf

# ── Price cache (5-minute TTL) ──
_price_cache = {}
_CACHE_TTL = 300  # seconds


def _fetch_price(symbol):
    """Fetch the current price for a symbol, with 5-minute caching."""
    now = time.time()
    cached = _price_cache.get(symbol)
    if cached and now - cached["ts"] < _CACHE_TTL:
        return cached["price"]
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = getattr(info, "last_price", None)
        if price is None:
            hist = ticker.history(period="1d")
            price = float(hist["Close"].iloc[-1]) if not hist.empty else None
    except Exception:
        price = None
    _price_cache[symbol] = {"price": price, "ts": now}
    return price


def _evaluate_alerts(alerts):
    """Check each alert against current prices and return enriched list."""
    results = []
    for alert in alerts:
        symbol = alert.get("symbol", "").upper()
        condition = alert.get("condition", "above")
        threshold = alert.get("threshold", 0)
        price = _fetch_price(symbol)
        triggered = False
        if price is not None:
            if condition == "above" and price >= threshold:
                triggered = True
            elif condition == "below" and price <= threshold:
                triggered = True
        results.append({
            **alert,
            "symbol": symbol,
            "current_price": round(price, 2) if price is not None else "N/A",
            "status": "Triggered" if triggered else "Active",
        })
    return results


def layout():
    return html.Div([
        # Persistent store for alerts (survives browser refresh)
        dcc.Store(id="alerts-store", storage_type="local", data=[]),

        # ── Triggered alerts banner ──
        html.Div(id="alerts-triggered-banner"),

        # ── KPI row ──
        html.Div(id="alerts-kpi-row", className="kpi-row"),

        # ── Alert creation form ──
        html.Div([
            html.H4("Create Alert"),
            html.Div([
                html.Div([
                    html.Label("Ticker Symbol"),
                    dcc.Input(
                        id="alert-symbol-input",
                        type="text",
                        placeholder="e.g. AAPL",
                        debounce=True,
                        style={"width": "140px", "padding": "6px 10px",
                               "borderRadius": "8px", "border": "1px solid var(--border-color, #ddd)"},
                    ),
                ], style={"display": "inline-block", "marginRight": "16px",
                          "verticalAlign": "top"}),
                html.Div([
                    html.Label("Condition"),
                    dcc.Dropdown(
                        id="alert-condition-dropdown",
                        options=[
                            {"label": "Price Above", "value": "above"},
                            {"label": "Price Below", "value": "below"},
                        ],
                        value="above",
                        clearable=False,
                        style={"width": "160px"},
                    ),
                ], style={"display": "inline-block", "marginRight": "16px",
                          "verticalAlign": "top"}),
                html.Div([
                    html.Label("Threshold"),
                    dcc.Input(
                        id="alert-threshold-input",
                        type="number",
                        placeholder="150.00",
                        debounce=True,
                        style={"width": "120px", "padding": "6px 10px",
                               "borderRadius": "8px", "border": "1px solid var(--border-color, #ddd)"},
                    ),
                ], style={"display": "inline-block", "marginRight": "16px",
                          "verticalAlign": "top"}),
                html.Div([
                    html.Button("Add Alert", id="alert-add-btn",
                                className="header-btn",
                                style={"marginTop": "24px"}),
                ], style={"display": "inline-block", "verticalAlign": "top"}),
            ]),
            html.Div(id="alert-form-feedback",
                     style={"color": Styles.strongRed, "fontSize": "13px",
                            "marginTop": "6px"}),
        ], className="card", style={"marginBottom": "20px", "padding": "16px"}),

        # ── Active alerts table ──
        html.Div([
            html.H4("Active Alerts"),
            dcc.Loading(
                html.Div(id="alerts-table-container"),
                type="dot",
            ),
        ], className="card", style={"padding": "16px"}),
    ])


def register_callbacks(app):

    # ── Add alert ──
    @app.callback(
        [Output("alerts-store", "data", allow_duplicate=True),
         Output("alert-form-feedback", "children"),
         Output("alert-symbol-input", "value"),
         Output("alert-threshold-input", "value")],
        [Input("alert-add-btn", "n_clicks")],
        [State("alert-symbol-input", "value"),
         State("alert-condition-dropdown", "value"),
         State("alert-threshold-input", "value"),
         State("alerts-store", "data")],
        prevent_initial_call=True,
    )
    def add_alert(n_clicks, symbol, condition, threshold, existing):
        if not n_clicks:
            return existing or [], "", symbol, threshold
        if not symbol or not symbol.strip():
            return existing or [], "Please enter a ticker symbol.", symbol, threshold
        if threshold is None:
            return existing or [], "Please enter a threshold value.", symbol, threshold
        try:
            threshold = float(threshold)
        except (ValueError, TypeError):
            return existing or [], "Threshold must be a number.", symbol, threshold

        alerts = list(existing or [])
        alerts.append({
            "symbol": symbol.strip().upper(),
            "condition": condition,
            "threshold": threshold,
        })
        return alerts, "", "", None

    # ── Delete alert (via active cell click on Delete column) ──
    @app.callback(
        Output("alerts-store", "data", allow_duplicate=True),
        [Input("alerts-datatable", "active_cell")],
        [State("alerts-datatable", "data"),
         State("alerts-store", "data")],
        prevent_initial_call=True,
    )
    def delete_alert(active_cell, table_data, stored):
        if not active_cell:
            return stored or []
        if active_cell.get("column_id") != "delete":
            return stored or []
        row_idx = active_cell["row"]
        alerts = list(stored or [])
        if 0 <= row_idx < len(alerts):
            alerts.pop(row_idx)
        return alerts

    # ── Render table, KPIs, and triggered banner ──
    @app.callback(
        [Output("alerts-table-container", "children"),
         Output("alerts-kpi-row", "children"),
         Output("alerts-triggered-banner", "children")],
        [Input("alerts-store", "data"),
         Input("url", "pathname")],
    )
    def render_alerts(alerts, _pathname):
        alerts = alerts or []
        if not alerts:
            kpis = html.Div([
                Styles.kpiboxes("Total Alerts", 0, Styles.colorPalette[0]),
                Styles.kpiboxes("Active", 0, Styles.colorPalette[1]),
                Styles.kpiboxes("Triggered", 0, Styles.colorPalette[2]),
            ], className="kpi-row")
            return (
                html.P("No alerts configured. Use the form above to add one."),
                kpis,
                html.Div(),
            )

        evaluated = _evaluate_alerts(alerts)

        # Build table data
        table_rows = []
        for i, a in enumerate(evaluated):
            table_rows.append({
                "symbol": a["symbol"],
                "condition": a["condition"].capitalize(),
                "threshold": a["threshold"],
                "status": a["status"],
                "current_price": a["current_price"],
                "delete": "\u2716",
            })

        table = dash_table.DataTable(
            id="alerts-datatable",
            columns=[
                {"name": "Symbol", "id": "symbol"},
                {"name": "Condition", "id": "condition"},
                {"name": "Threshold", "id": "threshold", "type": "numeric"},
                {"name": "Status", "id": "status"},
                {"name": "Current Price", "id": "current_price"},
                {"name": "", "id": "delete", "presentation": "markdown"},
            ],
            data=table_rows,
            sort_action="native",
            style_table={"overflowX": "auto"},
            style_cell={"padding": "8px", "textAlign": "left", "fontSize": "14px"},
            style_header={
                "fontWeight": "bold", "fontSize": "14px",
                "fontFamily": Styles.GRAPH_LAYOUT["font"]["family"],
            },
            style_data_conditional=[
                {"if": {"row_index": "odd"},
                 "backgroundColor": "var(--table-stripe, #f9f9f9)"},
                {"if": {"filter_query": '{status} = "Triggered"'},
                 "backgroundColor": "rgba(255, 59, 48, 0.08)"},
                {"if": {"column_id": "delete"},
                 "textAlign": "center", "cursor": "pointer", "color": Styles.strongRed},
            ],
        )

        # KPIs
        total = len(evaluated)
        triggered = sum(1 for a in evaluated if a["status"] == "Triggered")
        active = total - triggered

        kpis = html.Div([
            Styles.kpiboxes("Total Alerts", total, Styles.colorPalette[0]),
            Styles.kpiboxes("Active", active, Styles.colorPalette[1]),
            Styles.kpiboxes("Triggered", triggered, Styles.strongRed if triggered else Styles.colorPalette[2]),
        ], className="kpi-row")

        # Triggered banner badges
        triggered_alerts = [a for a in evaluated if a["status"] == "Triggered"]
        if triggered_alerts:
            badges = []
            for a in triggered_alerts:
                badges.append(html.Span(
                    f"{a['symbol']} {a['condition']} {a['threshold']} (now {a['current_price']})",
                    style={
                        "display": "inline-block",
                        "padding": "6px 14px",
                        "marginRight": "8px",
                        "marginBottom": "6px",
                        "borderRadius": "20px",
                        "backgroundColor": Styles.strongRed,
                        "color": "#fff",
                        "fontSize": "13px",
                        "fontWeight": "600",
                    },
                ))
            banner = html.Div([
                html.Div(badges, style={"padding": "12px 0"}),
            ], className="card",
                style={"marginBottom": "16px", "padding": "8px 16px",
                       "borderLeft": f"4px solid {Styles.strongRed}"})
        else:
            banner = html.Div()

        return table, kpis, banner
