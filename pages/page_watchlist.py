import time
import logging
import Styles
import yfinance as yf
from dash import dcc, html, Input, Output, State, dash_table, callback_context

logger = logging.getLogger(__name__)

# ── Simple in-memory cache: {ticker: {"data": dict, "ts": float}} ──
_cache = {}
_CACHE_TTL = 300  # 5 minutes


def _fetch_ticker_data(symbol):
    """Fetch current data for a single ticker via yfinance, with 5-min cache."""
    now = time.time()
    if symbol in _cache and now - _cache[symbol]["ts"] < _CACHE_TTL:
        return _cache[symbol]["data"]

    try:
        tk = yf.Ticker(symbol)
        info = tk.info or {}

        current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0
        change = current_price - prev_close if current_price and prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0

        row = {
            "Symbol": symbol.upper(),
            "Price": round(current_price, 2) if current_price else None,
            "Change": round(change, 2),
            "Change%": round(change_pct, 2),
            "52w Low": round(info.get("fiftyTwoWeekLow", 0) or 0, 2) or None,
            "52w High": round(info.get("fiftyTwoWeekHigh", 0) or 0, 2) or None,
            "P/E": round(info.get("trailingPE", 0) or 0, 2) or None,
            "Div Yield": round((info.get("dividendYield") or 0) * 100, 2) or None,
        }

        _cache[symbol] = {"data": row, "ts": now}
        return row

    except Exception as e:
        logger.warning("Failed to fetch watchlist data for %s: %s", symbol, e)
        return {
            "Symbol": symbol.upper(),
            "Price": None, "Change": None, "Change%": None,
            "52w Low": None, "52w High": None,
            "P/E": None, "Div Yield": None,
        }


def layout():
    return html.Div([
        # Persisted watchlist store
        dcc.Store(id="watchlist-store", storage_type="local", data=[]),

        # ── Add ticker row ──
        html.Div([
            html.Div([
                dcc.Input(
                    id="watchlist-input",
                    type="text",
                    placeholder="Enter ticker symbol (e.g. AAPL)",
                    debounce=True,
                    style={
                        "width": "220px", "padding": "8px 12px",
                        "borderRadius": "8px", "border": "1px solid #ccc",
                        "fontSize": "14px",
                    },
                ),
                html.Button("Add", id="watchlist-add-btn", n_clicks=0,
                            className="header-btn",
                            style={"marginLeft": "8px", "padding": "8px 20px"}),
            ], style={"display": "flex", "alignItems": "center", "gap": "4px"}),
            html.Div(id="watchlist-add-status",
                     style={"fontSize": "13px", "marginTop": "4px", "minHeight": "20px"}),
        ], style={"padding": "10px 15px"}),

        # ── KPI row ──
        html.Div(id="watchlist-kpis", children=Styles.skeleton_kpis(3)),

        # ── Data table ──
        dcc.Loading(
            html.Div(id="watchlist-table-container",
                     children=Styles.skeleton_table()),
            type="dot",
        ),
    ])


def register_callbacks(app):
    # ── Add / remove tickers from the store ──
    @app.callback(
        [Output("watchlist-store", "data"),
         Output("watchlist-input", "value"),
         Output("watchlist-add-status", "children")],
        [Input("watchlist-add-btn", "n_clicks"),
         Input("watchlist-input", "n_submit"),
         Input("watchlist-table", "active_cell")],
        [State("watchlist-input", "value"),
         State("watchlist-store", "data"),
         State("watchlist-table", "data")],
        prevent_initial_call=True,
    )
    def modify_watchlist(add_clicks, n_submit, active_cell, input_value, current_list, table_data):
        current_list = current_list or []
        ctx = callback_context
        if not ctx.triggered:
            return current_list, "", ""

        trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

        # ── Handle "Remove" click via active cell in the last column ──
        if trigger_id == "watchlist-table" and active_cell:
            if active_cell.get("column_id") == "Remove" and table_data:
                row_idx = active_cell["row"]
                symbol_to_remove = table_data[row_idx].get("Symbol", "").upper()
                new_list = [s for s in current_list if s.upper() != symbol_to_remove]
                return new_list, "", f"Removed {symbol_to_remove}"

        # ── Handle Add button or Enter key ──
        if trigger_id in ("watchlist-add-btn", "watchlist-input"):
            if not input_value or not input_value.strip():
                return current_list, "", "Please enter a ticker symbol."
            symbol = input_value.strip().upper()
            if symbol in [s.upper() for s in current_list]:
                return current_list, "", f"{symbol} is already in your watchlist."
            new_list = current_list + [symbol]
            return new_list, "", f"Added {symbol}"

        return current_list, "", ""

    # ── Render KPIs + table whenever the store changes ──
    @app.callback(
        [Output("watchlist-kpis", "children"),
         Output("watchlist-table-container", "children")],
        [Input("watchlist-store", "data")],
    )
    def update_watchlist_display(symbols):
        symbols = symbols or []

        if not symbols:
            return (
                html.Div([
                    Styles.kpiboxes("Watchlist Items", 0, Styles.colorPalette[0]),
                    Styles.kpiboxes("Avg P/E", "N/A", Styles.colorPalette[1]),
                    Styles.kpiboxes("Avg Div Yield", "N/A", Styles.colorPalette[2]),
                ], className="kpi-row"),
                Styles.empty_state("Your watchlist is empty. Add a ticker above to get started."),
            )

        # Fetch data for every symbol
        rows = [_fetch_ticker_data(s) for s in symbols]

        # Add a clickable Remove marker
        for r in rows:
            r["Remove"] = "\u2716"

        # KPI calculations
        pe_values = [r["P/E"] for r in rows if r["P/E"] is not None and r["P/E"] > 0]
        dy_values = [r["Div Yield"] for r in rows if r["Div Yield"] is not None and r["Div Yield"] > 0]
        avg_pe = sum(pe_values) / len(pe_values) if pe_values else 0
        avg_dy = sum(dy_values) / len(dy_values) if dy_values else 0

        kpis = html.Div([
            Styles.kpiboxes("Watchlist Items", len(symbols), Styles.colorPalette[0]),
            Styles.kpiboxes("Avg P/E", round(avg_pe, 1) if avg_pe else "N/A", Styles.colorPalette[1]),
            Styles.kpiboxes("Avg Div Yield", f"{avg_dy:.2f}%" if avg_dy else "N/A", Styles.colorPalette[2]),
        ], className="kpi-row")

        # Build DataTable
        columns = [
            {"name": "Symbol", "id": "Symbol"},
            {"name": "Price", "id": "Price", "type": "numeric",
             "format": dash_table.FormatTemplate.money(2)},
            {"name": "Change", "id": "Change", "type": "numeric"},
            {"name": "Change%", "id": "Change%", "type": "numeric"},
            {"name": "52w Low", "id": "52w Low", "type": "numeric"},
            {"name": "52w High", "id": "52w High", "type": "numeric"},
            {"name": "P/E", "id": "P/E", "type": "numeric"},
            {"name": "Div Yield", "id": "Div Yield", "type": "numeric"},
            {"name": "\u2716", "id": "Remove", "presentation": "markdown"},
        ]

        table = dash_table.DataTable(
            id="watchlist-table",
            columns=columns,
            data=rows,
            sort_action="native",
            page_size=25,
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
                # Green for positive change
                {"if": {"filter_query": "{Change} > 0", "column_id": "Change"},
                 "color": Styles.strongGreen, "fontWeight": "600"},
                {"if": {"filter_query": "{Change%} > 0", "column_id": "Change%"},
                 "color": Styles.strongGreen, "fontWeight": "600"},
                # Red for negative change
                {"if": {"filter_query": "{Change} < 0", "column_id": "Change"},
                 "color": Styles.strongRed, "fontWeight": "600"},
                {"if": {"filter_query": "{Change%} < 0", "column_id": "Change%"},
                 "color": Styles.strongRed, "fontWeight": "600"},
                # Remove column styling
                {"if": {"column_id": "Remove"},
                 "textAlign": "center", "cursor": "pointer", "color": Styles.strongRed},
            ],
        )

        return kpis, html.Div([table], className="card", style={"marginBottom": "20px"})
