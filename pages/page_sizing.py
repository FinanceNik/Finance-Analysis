"""Position Sizing Calculator – suggests how many shares to buy based on
portfolio constraints, volatility, and correlation with existing holdings."""

import time
import numpy as np
import pandas as pd
import yfinance as yf
from dash import dcc, html, Input, Output, State
import Styles
import dataLoadPositions as dlp

# ── Simple in-memory cache for yfinance lookups ──
_yf_cache: dict = {}
_YF_TTL = 300  # seconds


def _fetch_ticker_info(ticker: str) -> dict | None:
    """Fetch current price and 1-year daily history for *ticker* (cached 5 min)."""
    ticker = ticker.strip().upper()
    now = time.time()
    if ticker in _yf_cache and now - _yf_cache[ticker]["ts"] < _YF_TTL:
        return _yf_cache[ticker]["data"]
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1y")
        if hist.empty:
            return None
        price = float(hist["Close"].iloc[-1])
        data = {"price": price, "history": hist["Close"]}
        _yf_cache[ticker] = {"ts": now, "data": data}
        return data
    except Exception:
        return None


def _load_symbol_mapping() -> dict:
    try:
        mapping = pd.read_csv("data/mapping.csv", sep=",")
        return dict(zip(mapping["symbol"], mapping["ticker"]))
    except Exception:
        return {}


def _resolve_symbol(sym, available_cols, sym_to_ticker=None):
    if sym in available_cols:
        return sym
    if sym_to_ticker and sym_to_ticker.get(sym) and sym_to_ticker[sym] in available_cols:
        return sym_to_ticker[sym]
    matches = [c for c in available_cols if c.startswith(sym)]
    return matches[0] if matches else None


def _portfolio_vol_and_returns():
    """Return annualised portfolio volatility, per-holding daily returns DataFrame,
    and a weight Series keyed by historical-data column name."""
    df = dlp.add_position_pnl_columns()
    if df.empty:
        return None, pd.DataFrame(), pd.Series(dtype=float)

    total_mv = df["market_value"].sum()
    df["weight"] = df["market_value"] / total_mv

    try:
        hist = dlp.load_historical_data().reset_index()
        if "date" in hist.columns:
            hist = hist.set_index("date")
        hist = 10 ** hist
        hist = hist.groupby(hist.index).first().sort_index().ffill()
    except Exception:
        return None, pd.DataFrame(), pd.Series(dtype=float)

    sym_to_ticker = _load_symbol_mapping()
    holding_weights = {}
    for _, row in df.iterrows():
        sym = row.get("symbol", "")
        w = row.get("weight", 0)
        col = _resolve_symbol(sym, hist.columns, sym_to_ticker)
        if col:
            holding_weights[col] = holding_weights.get(col, 0) + w

    if not holding_weights:
        return None, pd.DataFrame(), pd.Series(dtype=float)

    matched_cols = list(holding_weights.keys())
    weights_s = pd.Series(holding_weights)
    weights_s = weights_s / weights_s.sum()

    subset = hist[matched_cols].dropna()
    daily_returns = subset.pct_change().iloc[1:]
    port_daily = (daily_returns * weights_s).sum(axis=1)
    port_vol = float(port_daily.std() * np.sqrt(252))

    return port_vol, daily_returns, weights_s


# ────────────────────────────────────────────────────────────
# Layout
# ────────────────────────────────────────────────────────────
def layout():
    return html.Div([
        html.H4("Position Sizing Calculator"),

        # ── Input section ──
        html.Div([
            html.Div([
                html.Label("Ticker Symbol"),
                dcc.Input(
                    id="sizing-ticker", type="text", placeholder="e.g. AAPL",
                    debounce=True,
                    style={"width": "120px", "padding": "6px 10px"},
                ),
            ], style={"display": "inline-block", "marginRight": "24px"}),

            html.Div([
                html.Label("Available Cash"),
                dcc.Input(
                    id="sizing-cash", type="number",
                    placeholder="10000", min=0,
                    style={"width": "140px", "padding": "6px 10px"},
                ),
            ], style={"display": "inline-block", "marginRight": "24px"}),

            html.Div([
                html.Label("Max Position Size (% of portfolio)"),
                dcc.Slider(
                    id="sizing-max-pct", min=1, max=25, step=0.5, value=5,
                    marks={i: f"{i}%" for i in [1, 5, 10, 15, 20, 25]},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ], style={"display": "inline-block", "width": "300px",
                       "verticalAlign": "top", "marginRight": "24px"}),

            html.Div([
                html.Label("Risk Tolerance"),
                dcc.Dropdown(
                    id="sizing-risk",
                    options=[
                        {"label": "Conservative (2%)", "value": 0.02},
                        {"label": "Moderate (5%)", "value": 0.05},
                        {"label": "Aggressive (10%)", "value": 0.10},
                    ],
                    value=0.05, clearable=False,
                    style={"width": "220px"},
                ),
            ], style={"display": "inline-block", "verticalAlign": "top"}),
        ], className="card", style={"padding": "20px", "marginBottom": "16px"}),

        # ── Results (callback-driven) ──
        dcc.Loading(
            html.Div(id="sizing-results", children=html.Div([
                Styles.skeleton_kpis(4),
                html.Div([Styles.skeleton_chart(), Styles.skeleton_chart()],
                          className="grid-2"),
            ])),
            type="dot",
        ),
    ])


# ────────────────────────────────────────────────────────────
# Callbacks
# ────────────────────────────────────────────────────────────
def register_callbacks(app):

    @app.callback(
        Output("sizing-results", "children"),
        [Input("sizing-ticker", "value"),
         Input("sizing-cash", "value"),
         Input("sizing-max-pct", "value"),
         Input("sizing-risk", "value")],
    )
    def update_sizing(ticker, cash, max_pct, risk_pct):
        if not ticker or not ticker.strip():
            return html.P("Enter a ticker symbol above to begin.",
                          style={"padding": "20px", "opacity": 0.6})

        ticker = ticker.strip().upper()

        # ── Fetch ticker data ──
        info = _fetch_ticker_info(ticker)
        if info is None:
            return html.P(f"Could not fetch data for '{ticker}'. "
                          "Check the symbol and try again.",
                          style={"padding": "20px", "color": Styles.strongRed})

        price = info["price"]
        new_hist = info["history"]

        # ── Portfolio data ──
        df = dlp.fetch_data()
        total_value = dlp.portfolio_total_value() if not df.empty else 0
        cash = cash if cash and cash > 0 else 0

        if total_value == 0 and cash == 0:
            return html.P("No portfolio data and no cash specified.",
                          style={"padding": "20px"})

        effective_portfolio = total_value + cash
        max_pct = max_pct if max_pct else 5
        risk_pct = risk_pct if risk_pct else 0.05

        # ── Constraint 1: max % of portfolio ──
        max_dollar = effective_portfolio * (max_pct / 100)

        # ── Portfolio volatility & correlations ──
        port_vol, daily_returns, weights_s = _portfolio_vol_and_returns()

        # New ticker daily returns (align to 1y)
        new_returns = new_hist.pct_change().dropna()
        new_vol = float(new_returns.std() * np.sqrt(252)) if len(new_returns) > 20 else None

        # Correlation with each existing holding
        correlations = {}
        avg_correlation = 0.0
        if not daily_returns.empty and len(new_returns) > 20:
            for col in daily_returns.columns:
                common = daily_returns[col].dropna()
                merged = pd.concat([common, new_returns], axis=1, join="inner")
                if len(merged) > 20:
                    correlations[col] = float(merged.iloc[:, 0].corr(merged.iloc[:, 1]))
            if correlations:
                # Weight-averaged correlation
                total_w = 0
                weighted_corr = 0
                for col, corr in correlations.items():
                    w = weights_s.get(col, 0)
                    weighted_corr += corr * w
                    total_w += w
                avg_correlation = weighted_corr / total_w if total_w > 0 else 0

        # ── Constraint 2: volatility-adjusted sizing ──
        # If new ticker is more volatile than portfolio, reduce allocation
        vol_scalar = 1.0
        if port_vol and new_vol and new_vol > 0:
            vol_scalar = min(port_vol / new_vol, 1.0)

        # ── Constraint 3: correlation penalty ──
        # Lower correlation = can allocate more (diversification benefit)
        corr_scalar = 1.0 - max(avg_correlation, 0) * 0.5  # 0.5..1.0

        # ── Risk-based limit ──
        risk_dollar = effective_portfolio * risk_pct

        # ── Combine constraints ──
        suggested_dollar = min(
            max_dollar,
            risk_dollar * vol_scalar * corr_scalar,
            cash if cash > 0 else float("inf"),
        )
        suggested_dollar = max(suggested_dollar, 0)

        suggested_shares = int(suggested_dollar // price) if price > 0 else 0
        actual_dollar = suggested_shares * price
        new_total = total_value + actual_dollar
        pct_of_portfolio = (actual_dollar / new_total * 100) if new_total > 0 else 0

        # ── New portfolio volatility estimate ──
        new_port_vol = port_vol  # fallback
        if port_vol is not None and new_vol is not None:
            # Simple 2-asset approximation:
            # w_new = actual_dollar / new_total
            w_new = actual_dollar / new_total if new_total > 0 else 0
            w_old = 1 - w_new
            new_port_vol = np.sqrt(
                (w_old * port_vol) ** 2
                + (w_new * new_vol) ** 2
                + 2 * w_old * w_new * port_vol * new_vol * avg_correlation
            )

        # ── KPIs ──
        kpi_row = html.Div([
            Styles.kpiboxes("Suggested Shares", suggested_shares, Styles.colorPalette[1]),
            Styles.kpiboxes("Dollar Amount", f"${actual_dollar:,.0f}", Styles.colorPalette[0]),
            Styles.kpiboxes(
                "New Portfolio Vol",
                f"{new_port_vol * 100:.1f}%" if new_port_vol is not None else "N/A",
                Styles.colorPalette[2],
            ),
            Styles.kpiboxes(
                "Correlation Score",
                f"{avg_correlation:.2f}",
                Styles.strongGreen if avg_correlation < 0.5 else Styles.strongRed,
            ),
        ], className="kpi-row")

        # ── Before / After allocation pie charts ──
        before_labels = []
        before_values = []
        if not df.empty and "symbol" in df.columns and "total_value" in df.columns:
            grouped = df.groupby("symbol")["total_value"].sum().sort_values(ascending=False)
            for sym, val in grouped.items():
                before_labels.append(sym)
                before_values.append(float(val))
        if cash and cash > 0:
            before_labels.append("Cash")
            before_values.append(float(cash))

        after_labels = list(before_labels)
        after_values = list(before_values)
        if ticker in after_labels:
            idx = after_labels.index(ticker)
            after_values[idx] += actual_dollar
        else:
            after_labels.append(ticker)
            after_values.append(actual_dollar)
        # Reduce cash by purchase amount
        if "Cash" in after_labels:
            ci = after_labels.index("Cash")
            after_values[ci] = max(after_values[ci] - actual_dollar, 0)

        pie_before = {
            "data": [{
                "type": "pie",
                "labels": before_labels,
                "values": before_values,
                "hole": 0.45,
                "textinfo": "label+percent",
                "textposition": "outside",
                "marker": {"colors": Styles.purple_list * 3},
            }],
            "layout": Styles.graph_layout(title="Before Purchase",
                                          showlegend=False,
                                          margin={"t": 40, "b": 20, "l": 20, "r": 20}),
        }

        pie_after = {
            "data": [{
                "type": "pie",
                "labels": after_labels,
                "values": after_values,
                "hole": 0.45,
                "textinfo": "label+percent",
                "textposition": "outside",
                "marker": {"colors": Styles.purple_list * 3},
            }],
            "layout": Styles.graph_layout(title="After Purchase",
                                          showlegend=False,
                                          margin={"t": 40, "b": 20, "l": 20, "r": 20}),
        }

        # ── Before / After portfolio volatility ──
        vol_labels = ["Before", "After"]
        vol_values = [
            port_vol * 100 if port_vol else 0,
            new_port_vol * 100 if new_port_vol else 0,
        ]
        vol_colors = [Styles.colorPalette[0], Styles.colorPalette[1]]

        vol_chart = {
            "data": [{
                "type": "bar",
                "x": vol_labels,
                "y": [round(v, 2) for v in vol_values],
                "marker": {"color": vol_colors},
                "text": [f"{v:.2f}%" for v in vol_values],
                "textposition": "outside",
            }],
            "layout": Styles.graph_layout(
                title="Portfolio Volatility Impact",
                yaxis={"title": "Annualised Volatility (%)"},
            ),
        }

        # ── Correlation with top 5 holdings ──
        top5_corr_labels = []
        top5_corr_values = []
        if correlations:
            sorted_corr = sorted(correlations.items(),
                                 key=lambda x: abs(x[1]), reverse=True)[:5]
            for col, corr in sorted_corr:
                top5_corr_labels.append(col)
                top5_corr_values.append(round(corr, 3))

        corr_colors = [
            Styles.strongGreen if abs(c) < 0.5 else Styles.strongRed
            for c in top5_corr_values
        ]

        corr_chart = {
            "data": [{
                "type": "bar",
                "x": top5_corr_labels,
                "y": top5_corr_values,
                "marker": {"color": corr_colors},
                "text": [f"{c:.2f}" for c in top5_corr_values],
                "textposition": "outside",
            }],
            "layout": Styles.graph_layout(
                title=f"Correlation of {ticker} with Top Holdings",
                yaxis={"title": "Correlation", "range": [-1, 1]},
            ),
        }

        # ── Assemble ──
        return html.Div([
            kpi_row,
            html.Div([
                html.Div([dcc.Graph(figure=pie_before)], className="card"),
                html.Div([dcc.Graph(figure=pie_after)], className="card"),
            ], className="grid-2"),
            html.Div([
                html.Div([dcc.Graph(figure=vol_chart)], className="card"),
                html.Div([dcc.Graph(figure=corr_chart)], className="card"),
            ], className="grid-2"),
        ])
