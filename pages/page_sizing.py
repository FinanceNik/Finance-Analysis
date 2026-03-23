"""Position Sizing Calculator — Kelly Criterion & fixed-fraction helpers."""
import re
import logging
import Styles
import yfinance as yf
from dash import dcc, html, Input, Output, State, callback_context
from dash.exceptions import PreventUpdate

logger = logging.getLogger(__name__)


def layout():
    return html.Div([
        html.Div([
            html.H4("Position Sizing Calculator"),
            html.P("Estimate optimal position size using the Kelly Criterion.",
                   className="page-subtitle"),
        ], className="page-header"),

        html.Div([
            html.Div([
                html.Label("Ticker Symbol"),
                dcc.Input(id="sizing-ticker", type="text",
                          placeholder="e.g. AAPL", debounce=True,
                          style={"width": "180px", "padding": "8px 12px",
                                 "borderRadius": "8px", "border": "1px solid #ccc"}),
            ], style={"marginRight": "20px"}),
            html.Div([
                html.Label("Available Cash"),
                dcc.Input(id="sizing-cash", type="number",
                          placeholder="e.g. 10000", min=0,
                          style={"width": "180px", "padding": "8px 12px",
                                 "borderRadius": "8px", "border": "1px solid #ccc"}),
            ], style={"marginRight": "20px"}),
            html.Div([
                html.Label("Win Probability (%)"),
                dcc.Input(id="sizing-win-prob", type="number",
                          value=55, min=1, max=99,
                          style={"width": "120px", "padding": "8px 12px",
                                 "borderRadius": "8px", "border": "1px solid #ccc"}),
            ], style={"marginRight": "20px"}),
            html.Button("Calculate", id="sizing-calc-btn", n_clicks=0,
                        className="header-btn",
                        style={"alignSelf": "flex-end", "padding": "8px 20px"}),
        ], style={"display": "flex", "alignItems": "flex-end", "gap": "8px",
                  "padding": "10px 15px", "flexWrap": "wrap"}),

        # Feedback / validation messages
        html.Div(id="sizing-feedback",
                 style={"padding": "0 15px", "fontSize": "13px", "minHeight": "20px"}),

        # Results area
        html.Div(id="sizing-results", style={"padding": "10px 15px"}),
    ])


def register_callbacks(app):
    @app.callback(
        [Output("sizing-results", "children"),
         Output("sizing-feedback", "children")],
        [Input("sizing-calc-btn", "n_clicks")],
        [State("sizing-ticker", "value"),
         State("sizing-cash", "value"),
         State("sizing-win-prob", "value")],
        prevent_initial_call=True,
    )
    def calculate_sizing(n_clicks, ticker, cash, win_prob):
        if not n_clicks:
            raise PreventUpdate

        # ── Input validation ──
        if not ticker or not ticker.strip():
            return "", html.Span("Please enter a ticker symbol.",
                                 style={"color": Styles.strongRed})

        ticker = ticker.strip().upper()
        if not re.match(r'^[A-Z0-9\.\^\-]{1,12}$', ticker):
            return "", html.Span("Invalid ticker format.",
                                 style={"color": Styles.strongRed})

        if cash is None or cash <= 0:
            return "", html.Span("Available cash must be greater than 0.",
                                 style={"color": Styles.strongRed})

        win_prob = win_prob or 55
        win_prob = max(1, min(99, win_prob))

        # ── Fetch current price ──
        try:
            tk = yf.Ticker(ticker)
            info = tk.info or {}
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if not price or price <= 0:
                return "", html.Span(
                    f"Ticker not found or no price data for {ticker}.",
                    style={"color": Styles.strongRed})
        except Exception as e:
            logger.warning("Sizing lookup failed for %s: %s", ticker, e)
            return "", html.Span(
                f"Ticker not found: could not retrieve data for {ticker}.",
                style={"color": Styles.strongRed})

        # ── Kelly Criterion ──
        p = win_prob / 100.0
        q = 1 - p
        # Assume 1:1 risk/reward for simplicity
        b = 1.0
        kelly_fraction = (p * b - q) / b if b > 0 else 0
        kelly_fraction = max(0, min(1, kelly_fraction))

        # Half-Kelly (more conservative)
        half_kelly = kelly_fraction / 2
        position_value = cash * half_kelly
        shares = int(position_value / price) if price > 0 else 0

        results = html.Div([
            html.Div([
                Styles.kpiboxes("Current Price", f"${price:,.2f}", Styles.colorPalette[0]),
                Styles.kpiboxes("Kelly %", f"{kelly_fraction * 100:.1f}%", Styles.colorPalette[1]),
                Styles.kpiboxes("Half-Kelly %", f"{half_kelly * 100:.1f}%", Styles.colorPalette[2]),
                Styles.kpiboxes("Shares to Buy", shares, Styles.colorPalette[3]),
            ], className="kpi-row"),
            html.Div([
                html.P(f"With ${cash:,.0f} available and a {win_prob}% win probability, "
                       f"the half-Kelly position size is ${position_value:,.0f} "
                       f"({shares} shares of {ticker} at ${price:,.2f})."),
            ], className="card", style={"padding": "16px", "marginTop": "12px"}),
        ])

        return results, ""
