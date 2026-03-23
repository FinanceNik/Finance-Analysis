"""Price Alerts — set threshold alerts for tickers (stored in browser localStorage)."""
import re
import logging
import Styles
from dash import dcc, html, Input, Output, State, dash_table, callback_context
from dash.exceptions import PreventUpdate

logger = logging.getLogger(__name__)


def layout():
    return html.Div([
        dcc.Store(id="alerts-store", storage_type="local", data=[]),

        html.Div([
            html.H4("Price Alerts"),
            html.P("Set price thresholds and get notified when they trigger.",
                   className="page-subtitle"),
        ], className="page-header"),

        # ── Add alert row ──
        html.Div([
            html.Div([
                html.Label("Ticker"),
                dcc.Input(id="alerts-ticker", type="text",
                          placeholder="e.g. AAPL", debounce=True,
                          style={"width": "140px", "padding": "8px 12px",
                                 "borderRadius": "8px", "border": "1px solid #ccc"}),
            ], style={"marginRight": "12px"}),
            html.Div([
                html.Label("Direction"),
                dcc.Dropdown(id="alerts-direction",
                             options=[{"label": "Above", "value": "above"},
                                      {"label": "Below", "value": "below"}],
                             value="above",
                             style={"width": "120px"},
                             clearable=False),
            ], style={"marginRight": "12px"}),
            html.Div([
                html.Label("Threshold ($)"),
                dcc.Input(id="alerts-threshold", type="number",
                          placeholder="e.g. 150.00", min=0, step=0.01,
                          style={"width": "140px", "padding": "8px 12px",
                                 "borderRadius": "8px", "border": "1px solid #ccc"}),
            ], style={"marginRight": "12px"}),
            html.Button("Add Alert", id="alerts-add-btn", n_clicks=0,
                        className="header-btn",
                        style={"alignSelf": "flex-end", "padding": "8px 20px"}),
        ], style={"display": "flex", "alignItems": "flex-end", "gap": "8px",
                  "padding": "10px 15px", "flexWrap": "wrap"}),

        # Feedback
        html.Div(id="alerts-feedback",
                 style={"padding": "0 15px", "fontSize": "13px", "minHeight": "20px"}),

        # Alerts table
        html.Div(id="alerts-table-container",
                 children=Styles.empty_state("No alerts configured yet.")),
    ])


def register_callbacks(app):
    @app.callback(
        [Output("alerts-store", "data"),
         Output("alerts-ticker", "value"),
         Output("alerts-threshold", "value"),
         Output("alerts-feedback", "children")],
        [Input("alerts-add-btn", "n_clicks")],
        [State("alerts-ticker", "value"),
         State("alerts-direction", "value"),
         State("alerts-threshold", "value"),
         State("alerts-store", "data")],
        prevent_initial_call=True,
    )
    def add_alert(n_clicks, ticker, direction, threshold, current_alerts):
        if not n_clicks:
            raise PreventUpdate

        current_alerts = current_alerts or []

        # ── Validation ──
        if not ticker or not ticker.strip():
            return current_alerts, ticker, threshold, html.Span(
                "Please enter a ticker symbol.",
                style={"color": Styles.strongRed})

        ticker = ticker.strip().upper()
        if not re.match(r'^[A-Z0-9\.\^\-]{1,12}$', ticker):
            return current_alerts, ticker, threshold, html.Span(
                "Invalid ticker format. Use letters, numbers, hyphens.",
                style={"color": Styles.strongRed})

        if threshold is None or threshold <= 0:
            return current_alerts, ticker, threshold, html.Span(
                "Threshold must be a positive number.",
                style={"color": Styles.strongRed})

        # Add the alert
        alert = {"ticker": ticker, "direction": direction, "threshold": threshold}
        current_alerts.append(alert)

        return current_alerts, "", None, html.Span(
            f"Alert added: {ticker} {direction} ${threshold:,.2f}",
            style={"color": Styles.strongGreen})

    @app.callback(
        Output("alerts-table-container", "children"),
        [Input("alerts-store", "data")],
    )
    def render_alerts_table(alerts):
        alerts = alerts or []
        if not alerts:
            return Styles.empty_state("No alerts configured yet.")

        columns = [
            {"name": "Ticker", "id": "ticker"},
            {"name": "Direction", "id": "direction"},
            {"name": "Threshold", "id": "threshold", "type": "numeric"},
        ]

        table = dash_table.DataTable(
            id="alerts-table",
            columns=columns,
            data=alerts,
            style_table={"overflowX": "auto"},
            style_cell={
                "padding": "8px", "textAlign": "left", "fontSize": "14px",
                "fontFamily": Styles.GRAPH_LAYOUT["font"]["family"],
            },
            style_header={
                "backgroundColor": Styles.colorPalette[0], "color": "white",
                "fontWeight": "bold", "fontSize": "14px",
                "fontFamily": Styles.GRAPH_LAYOUT["font"]["family"],
            },
            style_data_conditional=[
                {"if": {"row_index": "odd"},
                 "backgroundColor": "var(--table-stripe, #f9f9f9)"},
            ],
        )

        return html.Div([table], className="card", style={"margin": "10px 15px"})
