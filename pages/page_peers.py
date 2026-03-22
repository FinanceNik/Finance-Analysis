"""Peer Comparison page — compare a holding against sector peers."""

import time
import logging
import Styles
import dataLoadPositions as dlp
from dash import dcc, html, Input, Output, State, dash_table, no_update
import plotly.graph_objects as go
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ── 5-minute cache for yfinance data ──
_cache = {}
_CACHE_TTL = 300  # seconds


def _cached_info(ticker: str) -> dict:
    """Fetch yfinance .info with a 5-min TTL cache."""
    key = f"info_{ticker}"
    now = time.time()
    if key in _cache and now - _cache[key]["ts"] < _CACHE_TTL:
        return _cache[key]["data"]
    try:
        data = yf.Ticker(ticker).info or {}
    except Exception:
        data = {}
    _cache[key] = {"ts": now, "data": data}
    return data


def _cached_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Fetch yfinance .history() with a 5-min TTL cache."""
    key = f"hist_{ticker}_{period}"
    now = time.time()
    if key in _cache and now - _cache[key]["ts"] < _CACHE_TTL:
        return _cache[key]["data"]
    try:
        data = yf.Ticker(ticker).history(period=period)
    except Exception:
        data = pd.DataFrame()
    _cache[key] = {"ts": now, "data": data}
    return data


def _get_peer_tickers(ticker: str) -> list:
    """Attempt to find 3-5 sector peers via yfinance sector/industry info."""
    info = _cached_info(ticker)
    sector = info.get("sector", "")
    industry = info.get("industry", "")
    if not sector:
        return []

    # Common sector-to-peer mapping as fallback heuristic
    _SECTOR_PEERS = {
        "Technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMZN", "CRM", "ADBE", "INTC", "ORCL"],
        "Financial Services": ["JPM", "BAC", "GS", "MS", "C", "WFC", "BLK", "SCHW", "AXP", "USB"],
        "Healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "TMO", "ABT", "LLY", "BMY", "AMGN"],
        "Consumer Cyclical": ["AMZN", "TSLA", "HD", "NKE", "MCD", "SBUX", "LOW", "TJX", "BKNG", "CMG"],
        "Consumer Defensive": ["PG", "KO", "PEP", "WMT", "COST", "PM", "MO", "CL", "MDLZ", "GIS"],
        "Communication Services": ["GOOGL", "META", "DIS", "NFLX", "CMCSA", "VZ", "T", "TMUS", "ATVI", "EA"],
        "Industrials": ["HON", "UPS", "CAT", "BA", "GE", "MMM", "RTX", "LMT", "DE", "UNP"],
        "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "PXD"],
        "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "ED", "WEC"],
        "Real Estate": ["AMT", "PLD", "CCI", "EQIX", "SPG", "O", "PSA", "WELL", "DLR", "AVB"],
        "Basic Materials": ["LIN", "APD", "SHW", "ECL", "FCX", "NEM", "NUE", "DOW", "DD", "PPG"],
    }

    peers = _SECTOR_PEERS.get(sector, [])
    # Remove the ticker itself and limit to 5
    peers = [p for p in peers if p.upper() != ticker.upper()][:5]
    return peers


def _fmt(val, fmt_type="number"):
    """Format a value for display."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "N/A"
    if fmt_type == "pct":
        return f"{val:.2f}%"
    if fmt_type == "cap":
        if val >= 1e12:
            return f"${val / 1e12:.2f}T"
        if val >= 1e9:
            return f"${val / 1e9:.2f}B"
        if val >= 1e6:
            return f"${val / 1e6:.1f}M"
        return f"${val:,.0f}"
    if fmt_type == "price":
        return f"${val:,.2f}"
    if fmt_type == "ratio":
        return f"{val:.2f}"
    return str(val)


def _build_comparison_data(tickers: list) -> pd.DataFrame:
    """Build a comparison DataFrame for the given tickers."""
    rows = []
    for t in tickers:
        info = _cached_info(t)
        hist = _cached_history(t, "1y")
        perf_52w = None
        if not hist.empty and len(hist) > 1:
            perf_52w = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100

        rows.append({
            "Ticker": t.upper(),
            "Name": info.get("shortName", t.upper()),
            "Price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "Market Cap": info.get("marketCap"),
            "P/E": info.get("trailingPE"),
            "Forward P/E": info.get("forwardPE"),
            "Div Yield (%)": (info.get("dividendYield") or 0) * 100 if info.get("dividendYield") else None,
            "52w Perf (%)": perf_52w,
            "Beta": info.get("beta"),
        })
    return pd.DataFrame(rows)


def layout():
    """Return the page layout."""
    # Get holding symbols from positions data
    df = dlp.fetch_data()
    if df.empty or "symbol" not in df.columns:
        symbols = []
    else:
        symbols = sorted(df["symbol"].dropna().unique().tolist())

    holding_options = [{"label": s, "value": s} for s in symbols]

    return html.Div([
        # ── Controls row ──
        html.Div([
            html.Div([
                html.Label("Select Holding"),
                dcc.Dropdown(
                    id="peers-holding-select",
                    options=holding_options,
                    value=symbols[0] if symbols else None,
                    clearable=False,
                    style={"width": "200px"},
                ),
            ], style={"display": "inline-block", "verticalAlign": "top",
                       "padding": "10px 15px"}),
            html.Div([
                html.Label("Peer Tickers (auto-detected or enter manually, comma-separated)"),
                dcc.Input(
                    id="peers-manual-input",
                    type="text",
                    placeholder="e.g. AAPL, MSFT, GOOGL",
                    debounce=True,
                    style={"width": "350px", "padding": "6px 10px",
                           "borderRadius": "8px", "border": "1px solid var(--border, #ddd)"},
                ),
            ], style={"display": "inline-block", "verticalAlign": "top",
                       "padding": "10px 15px"}),
            html.Div([
                html.Button("Compare", id="peers-compare-btn",
                            className="header-btn",
                            style={"marginTop": "24px"}),
            ], style={"display": "inline-block", "verticalAlign": "top",
                       "padding": "10px 15px"}),
        ]),

        # ── KPI row ──
        dcc.Loading(
            html.Div(id="peers-kpi-row", children=Styles.skeleton_kpis(3)),
            type="dot",
        ),

        # ── Comparison table ──
        dcc.Loading(
            html.Div(id="peers-table-container", children=Styles.skeleton_table(),
                      className="card", style={"marginBottom": "20px"}),
            type="dot",
        ),

        # ── Charts row ──
        html.Div([
            html.Div([
                dcc.Loading(dcc.Graph(id="peers-bar-chart"), type="dot"),
            ], className="card"),
            html.Div([
                dcc.Loading(dcc.Graph(id="peers-price-chart"), type="dot"),
            ], className="card"),
        ], className="grid-2" if True else "grid-3",
           style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"}),
    ])


def register_callbacks(app):
    @app.callback(
        [Output("peers-manual-input", "value"),
         Output("peers-manual-input", "placeholder")],
        [Input("peers-holding-select", "value")],
        prevent_initial_call=True,
    )
    def auto_detect_peers(holding):
        """Auto-detect peers when a holding is selected."""
        if not holding:
            return "", "e.g. AAPL, MSFT, GOOGL"
        peers = _get_peer_tickers(holding)
        if peers:
            return ", ".join(peers), "Auto-detected peers (edit to override)"
        return "", "Could not detect peers — enter tickers manually"

    @app.callback(
        [Output("peers-kpi-row", "children"),
         Output("peers-table-container", "children"),
         Output("peers-bar-chart", "figure"),
         Output("peers-price-chart", "figure")],
        [Input("peers-compare-btn", "n_clicks")],
        [State("peers-holding-select", "value"),
         State("peers-manual-input", "value")],
        prevent_initial_call=True,
    )
    def update_peer_comparison(n_clicks, holding, manual_peers):
        if not holding:
            empty_fig = {"data": [], "layout": Styles.graph_layout(title="Select a holding")}
            return html.P("Select a holding first."), html.P(""), empty_fig, empty_fig

        # Parse peer tickers
        if manual_peers and manual_peers.strip():
            peer_tickers = [t.strip().upper() for t in manual_peers.split(",") if t.strip()]
        else:
            peer_tickers = _get_peer_tickers(holding)

        if not peer_tickers:
            empty_fig = {"data": [], "layout": Styles.graph_layout(
                title="No peers found — enter tickers manually")}
            return (html.P("No peers detected. Enter peer tickers manually."),
                    html.P(""), empty_fig, empty_fig)

        all_tickers = [holding.upper()] + [t for t in peer_tickers if t != holding.upper()]
        comp_df = _build_comparison_data(all_tickers)

        # ── KPIs: holding's rank among peers ──
        holding_row = comp_df[comp_df["Ticker"] == holding.upper()]
        kpi_children = []

        for metric, label, lower_better in [
            ("P/E", "P/E Rank", True),
            ("Div Yield (%)", "Yield Rank", False),
            ("52w Perf (%)", "Perf Rank", False),
        ]:
            valid = comp_df[metric].dropna()
            if not valid.empty and not holding_row.empty:
                val = holding_row[metric].values[0]
                if pd.notna(val):
                    if lower_better:
                        rank = int((comp_df[metric].dropna().rank().loc[holding_row.index[0]]))
                    else:
                        rank = int((comp_df[metric].dropna().rank(ascending=False)
                                    .loc[holding_row.index[0]]))
                    total = int(valid.count())
                    color = Styles.strongGreen if rank <= 2 else (
                        Styles.colorPalette[0] if rank <= 3 else Styles.strongRed)
                    kpi_children.append(
                        Styles.kpiboxes(f"{label} ({holding.upper()})",
                                        f"#{rank} of {total}", color))
                else:
                    kpi_children.append(Styles.kpiboxes(label, "N/A", Styles.colorPalette[0]))
            else:
                kpi_children.append(Styles.kpiboxes(label, "N/A", Styles.colorPalette[0]))

        kpi_row = html.Div(kpi_children, className="kpi-row")

        # ── Comparison table ──
        display_df = comp_df.copy()
        # Format columns for display
        for col, ft in [("Price", "price"), ("Market Cap", "cap"), ("P/E", "ratio"),
                        ("Forward P/E", "ratio"), ("Div Yield (%)", "pct"),
                        ("52w Perf (%)", "pct"), ("Beta", "ratio")]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda v: _fmt(v, ft))

        table = dash_table.DataTable(
            id="peers-comparison-table",
            columns=[{"name": c, "id": c} for c in display_df.columns],
            data=display_df.to_dict("records"),
            sort_action="native",
            style_table={"overflowX": "auto"},
            style_cell={"padding": "8px", "textAlign": "left", "fontSize": "14px"},
            style_header={"fontWeight": "bold", "fontSize": "14px",
                          "fontFamily": Styles.GRAPH_LAYOUT["font"]["family"]},
            style_data_conditional=[
                {"if": {"row_index": "odd"},
                 "backgroundColor": "var(--table-stripe, #f9f9f9)"},
                {"if": {"filter_query": '{Ticker} eq "' + holding.upper() + '"'},
                 "fontWeight": "bold",
                 "backgroundColor": "var(--accent-subtle, rgba(0,141,213,0.08))"},
            ],
        )

        # ── Grouped bar chart ──
        bar_metrics = ["P/E", "Forward P/E", "Div Yield (%)", "Beta"]
        bar_fig = go.Figure()
        colors = Styles.purple_list
        for i, ticker in enumerate(all_tickers):
            row = comp_df[comp_df["Ticker"] == ticker]
            if row.empty:
                continue
            vals = [row[m].values[0] if pd.notna(row[m].values[0]) else 0 for m in bar_metrics]
            bar_fig.add_trace(go.Bar(
                name=ticker,
                x=bar_metrics,
                y=vals,
                marker_color=colors[i % len(colors)],
            ))
        bar_fig.update_layout(
            **Styles.graph_layout(title="Key Metrics Comparison"),
            barmode="group",
            legend=dict(orientation="h", y=-0.15),
        )

        # ── Normalized price performance chart (1yr, indexed to 100) ──
        price_fig = go.Figure()
        for i, ticker in enumerate(all_tickers):
            hist = _cached_history(ticker, "1y")
            if hist.empty:
                continue
            normalized = (hist["Close"] / hist["Close"].iloc[0]) * 100
            price_fig.add_trace(go.Scatter(
                x=hist.index,
                y=normalized,
                mode="lines",
                name=ticker,
                line=dict(color=colors[i % len(colors)], width=2),
            ))
        price_fig.update_layout(
            **Styles.graph_layout(
                title="Normalized Price Performance (1Y, indexed to 100)",
                xaxis={"title": "Date", "type": "date"},
                yaxis={"title": "Indexed Price (100 = start)"},
            ),
            legend=dict(orientation="h", y=-0.15),
            hovermode="x unified",
        )

        return kpi_row, table, bar_fig, price_fig
