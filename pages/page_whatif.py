"""What-If Trade Simulator — simulate a sell+buy and see portfolio impact."""

import time
import numpy as np
import pandas as pd
import yfinance as yf
from dash import dcc, html, Input, Output, State
import Styles
import config
import dataLoadPositions as dlp

# ── 5-minute cache for yfinance lookups ──
_yf_cache = {}
_YF_CACHE_TTL = 300  # seconds


def _yf_lookup(ticker: str) -> dict | None:
    """Fetch price, dividend yield, and sector for a ticker with 5-min cache."""
    now = time.time()
    key = ticker.upper().strip()
    if key in _yf_cache and now - _yf_cache[key]["ts"] < _YF_CACHE_TTL:
        return _yf_cache[key]["data"]
    try:
        t = yf.Ticker(key)
        info = t.info or {}
        price = info.get("regularMarketPrice") or info.get("previousClose")
        if price is None:
            hist = t.history(period="5d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
        result = {
            "price": float(price) if price else None,
            "dividend_yield": float(info.get("dividendYield") or 0),
            "name": info.get("shortName", key),
        }
        _yf_cache[key] = {"data": result, "ts": now}
        return result
    except Exception:
        return None


def _load_symbol_mapping() -> dict:
    """Load broker-symbol to Yahoo-ticker mapping."""
    try:
        mapping = pd.read_csv("data/mapping.csv", sep=",")
        return dict(zip(mapping["symbol"], mapping["ticker"]))
    except Exception:
        return {}


def _portfolio_volatility(weights: np.ndarray, cov: pd.DataFrame) -> float:
    """Annualised portfolio volatility from weights and covariance matrix."""
    w = weights / weights.sum()
    port_var = w @ cov.values @ w
    return float(np.sqrt(port_var))


def _compute_hhi(market_values: pd.Series) -> float:
    """Herfindahl-Hirschman Index from market values."""
    total = market_values.sum()
    if total == 0:
        return 0.0
    weights = market_values / total
    return float(np.sum(weights ** 2))


# ─────────────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────────────
def layout():
    df = dlp.fetch_data()
    if df.empty:
        return html.Div(html.H4("No portfolio data available."))

    symbols = sorted(df["symbol"].dropna().unique().tolist())
    symbol_options = [{"label": s, "value": s} for s in symbols]

    return html.Div([
        html.H4("What-If Trade Simulator"),

        # ── Trade input card ──
        html.Div([
            html.Div([
                # Sell side
                html.Div([
                    html.H5("Sell", style={"color": Styles.strongRed, "margin": "0 0 10px 0"}),
                    html.Label("Holding"),
                    dcc.Dropdown(
                        id="whatif-sell-ticker",
                        options=symbol_options,
                        placeholder="Select holding to sell",
                        style={"marginBottom": "8px"},
                    ),
                    html.Label("Quantity to sell"),
                    dcc.Input(
                        id="whatif-sell-qty",
                        type="number", min=0, step=1, value=0,
                        style={"width": "100%", "padding": "6px", "marginBottom": "4px"},
                    ),
                    html.Div(id="whatif-sell-hint",
                             style={"fontSize": "12px", "color": "var(--text-secondary)"}),
                ], style={"flex": "1", "padding": "0 12px 0 0"}),

                # Buy side
                html.Div([
                    html.H5("Buy", style={"color": Styles.strongGreen, "margin": "0 0 10px 0"}),
                    html.Label("Ticker"),
                    dcc.Input(
                        id="whatif-buy-ticker",
                        type="text", placeholder="e.g. AAPL",
                        debounce=True,
                        style={"width": "100%", "padding": "6px", "marginBottom": "8px"},
                    ),
                    html.Label("Quantity to buy"),
                    dcc.Input(
                        id="whatif-buy-qty",
                        type="number", min=0, step=1, value=0,
                        style={"width": "100%", "padding": "6px", "marginBottom": "4px"},
                    ),
                    html.Div(id="whatif-buy-hint",
                             style={"fontSize": "12px", "color": "var(--text-secondary)"}),
                ], style={"flex": "1", "padding": "0 0 0 12px"}),
            ], style={"display": "flex", "gap": "12px"}),

            html.Button(
                "Simulate Trade",
                id="whatif-simulate-btn",
                className="header-btn",
                style={"marginTop": "16px", "width": "100%"},
            ),
        ], className="card", style={"padding": "20px", "marginBottom": "16px"}),

        # ── Results area ──
        dcc.Loading(
            html.Div(id="whatif-results"),
            type="dot",
        ),
    ])


# ─────────────────────────────────────────────────────
# Callbacks
# ─────────────────────────────────────────────────────
def register_callbacks(app):

    # Hint showing max quantity available for sell
    @app.callback(
        Output("whatif-sell-hint", "children"),
        Input("whatif-sell-ticker", "value"),
    )
    def sell_hint(sell_sym):
        if not sell_sym:
            return ""
        df = dlp.fetch_data()
        row = df[df["symbol"] == sell_sym]
        if row.empty:
            return ""
        qty = row["quantity"].iloc[0]
        price = row["price"].iloc[0]
        return f"You hold {qty:,.2f} units @ {price:,.2f} each"

    # Hint showing live price of buy ticker
    @app.callback(
        Output("whatif-buy-hint", "children"),
        Input("whatif-buy-ticker", "value"),
    )
    def buy_hint(buy_ticker):
        if not buy_ticker or len(buy_ticker.strip()) < 1:
            return ""
        info = _yf_lookup(buy_ticker.strip())
        if not info or info["price"] is None:
            return "Ticker not found"
        return f"{info['name']} — current price: {info['price']:,.2f}"

    # ── Main simulation ──
    @app.callback(
        Output("whatif-results", "children"),
        Input("whatif-simulate-btn", "n_clicks"),
        [State("whatif-sell-ticker", "value"),
         State("whatif-sell-qty", "value"),
         State("whatif-buy-ticker", "value"),
         State("whatif-buy-qty", "value")],
        prevent_initial_call=True,
    )
    def run_simulation(n_clicks, sell_sym, sell_qty, buy_ticker, buy_qty):
        if not n_clicks:
            return html.Div()

        # ── Validate inputs ──
        sell_qty = float(sell_qty or 0)
        buy_qty = float(buy_qty or 0)

        if not sell_sym and (not buy_ticker or buy_qty <= 0):
            return html.Div("Enter a sell and/or buy trade to simulate.",
                            className="card", style={"padding": "16px"})

        df = dlp.fetch_data().copy()
        if df.empty:
            return html.Div("No portfolio data.", className="card",
                            style={"padding": "16px"})

        sym_map = _load_symbol_mapping()
        geo_map = {**config.GEO_MAP}

        # Current state
        total_mv_before = df["total_value"].sum()

        # ── Sell logic ──
        sell_price = 0
        sell_value = 0
        if sell_sym and sell_qty > 0:
            idx = df.index[df["symbol"] == sell_sym]
            if len(idx) == 0:
                return _error("Sell ticker not found in portfolio.")
            i = idx[0]
            available = df.at[i, "quantity"]
            if sell_qty > available:
                return _error(f"Cannot sell {sell_qty} — you only hold {available:.2f}.")
            sell_price = df.at[i, "price"]
            sell_value = sell_qty * sell_price
            new_qty = available - sell_qty
            if new_qty <= 0:
                df = df.drop(i).reset_index(drop=True)
            else:
                df.at[i, "quantity"] = new_qty
                df.at[i, "total_value"] = new_qty * sell_price

        # ── Buy logic ──
        buy_price = 0
        buy_value = 0
        buy_name = ""
        buy_div_yield = 0
        if buy_ticker and buy_qty > 0:
            buy_ticker = buy_ticker.strip().upper()
            info = _yf_lookup(buy_ticker)
            if not info or info["price"] is None:
                return _error(f"Could not fetch price for {buy_ticker}.")
            buy_price = info["price"]
            buy_value = buy_qty * buy_price
            buy_name = info["name"]
            buy_div_yield = info["dividend_yield"]

            # Add / merge into portfolio
            existing = df.index[df["symbol"] == buy_ticker]
            if len(existing) > 0:
                j = existing[0]
                df.at[j, "quantity"] += buy_qty
                df.at[j, "total_value"] = df.at[j, "quantity"] * buy_price
            else:
                geo = geo_map.get(buy_ticker, "Other")
                new_row = {
                    "symbol": buy_ticker,
                    "quantity": buy_qty,
                    "price": buy_price,
                    "unit_cost": buy_price,
                    "total_value": buy_value,
                    "geography": geo,
                    "currency": "USD",
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        total_mv_after = df["total_value"].sum()

        # ── Geography allocation (before / after) ──
        df_before = dlp.fetch_data()
        geo_before = df_before.groupby("geography")["total_value"].sum()
        geo_after = df.groupby("geography")["total_value"].sum() if "geography" in df.columns else pd.Series(dtype=float)

        all_geos = sorted(set(geo_before.index.tolist() + geo_after.index.tolist()))
        before_vals = [geo_before.get(g, 0) for g in all_geos]
        after_vals = [geo_after.get(g, 0) for g in all_geos]
        before_total = sum(before_vals) or 1
        after_total = sum(after_vals) or 1

        donut_before = {
            "data": [{
                "type": "pie",
                "labels": all_geos,
                "values": before_vals,
                "hole": 0.55,
                "marker": {"colors": Styles.purple_list[:len(all_geos)]},
                "textinfo": "label+percent",
                "textposition": "outside",
            }],
            "layout": Styles.graph_layout(
                title="Current Allocation",
                showlegend=False,
                margin={"t": 40, "b": 20, "l": 20, "r": 20},
            ),
        }

        donut_after = {
            "data": [{
                "type": "pie",
                "labels": all_geos,
                "values": after_vals,
                "hole": 0.55,
                "marker": {"colors": Styles.purple_list[:len(all_geos)]},
                "textinfo": "label+percent",
                "textposition": "outside",
            }],
            "layout": Styles.graph_layout(
                title="After Trade",
                showlegend=False,
                margin={"t": 40, "b": 20, "l": 20, "r": 20},
            ),
        }

        # ── Risk: portfolio volatility before/after ──
        vol_before = None
        vol_after = None
        try:
            hist = dlp.load_historical_data().reset_index()
            if "date" in hist.columns:
                hist = hist.set_index("date")
            hist = 10 ** hist
            hist = hist.groupby(hist.index).first().sort_index().ffill()
            daily_ret = hist.pct_change().iloc[1:]

            def _build_weights(pos_df, returns_df):
                w_map = {}
                for _, row in pos_df.iterrows():
                    sym = row.get("symbol", "")
                    mv = row.get("total_value", 0)
                    col = sym
                    if sym not in returns_df.columns:
                        mapped = sym_map.get(sym)
                        if mapped and mapped in returns_df.columns:
                            col = mapped
                        else:
                            continue
                    w_map[col] = w_map.get(col, 0) + mv
                return w_map

            # Before
            wb = _build_weights(df_before, daily_ret)
            if wb:
                cols_b = list(wb.keys())
                w_arr_b = np.array([wb[c] for c in cols_b])
                w_arr_b = w_arr_b / w_arr_b.sum()
                cov_b = daily_ret[cols_b].dropna().cov() * 252
                vol_before = _portfolio_volatility(w_arr_b, cov_b)

            # After
            wa = _build_weights(df, daily_ret)
            if wa:
                cols_a = list(wa.keys())
                w_arr_a = np.array([wa[c] for c in cols_a])
                w_arr_a = w_arr_a / w_arr_a.sum()
                cov_a = daily_ret[cols_a].dropna().cov() * 252
                vol_after = _portfolio_volatility(w_arr_a, cov_a)
        except Exception:
            pass

        # ── Dividend impact ──
        div_before = 0
        div_after = 0
        try:
            for _, row in df_before.iterrows():
                sym = row["symbol"]
                mv = row.get("total_value", 0)
                ticker_str = sym_map.get(sym, sym)
                info = _yf_lookup(ticker_str)
                if info:
                    div_before += mv * info["dividend_yield"]

            for _, row in df.iterrows():
                sym = row["symbol"]
                mv = row.get("total_value", 0)
                ticker_str = sym_map.get(sym, sym)
                info = _yf_lookup(ticker_str)
                if info:
                    div_after += mv * info["dividend_yield"]
        except Exception:
            pass

        # ── Concentration (HHI) ──
        hhi_before = _compute_hhi(df_before["total_value"])
        hhi_after = _compute_hhi(df["total_value"])

        # ── Build result cards ──
        vol_change_pct = None
        if vol_before and vol_after:
            vol_change_pct = (vol_after - vol_before) / vol_before * 100

        div_change = div_after - div_before

        # Trade details card
        details_parts = []
        if sell_sym and sell_qty > 0:
            details_parts.append(
                f"Sell {sell_qty:,.0f} shares of {sell_sym} at {sell_price:,.2f}"
            )
        if buy_ticker and buy_qty > 0:
            details_parts.append(
                f"Buy {buy_qty:,.0f} shares of {buy_ticker} at {buy_price:,.2f}"
            )
        trade_detail_text = "  |  ".join(details_parts) if details_parts else "No trade specified"

        trade_card = html.Div([
            html.H5("Trade Details", style={"margin": "0 0 8px 0"}),
            html.P(trade_detail_text, style={"fontSize": "14px", "margin": 0}),
        ], className="card", style={
            "padding": "16px", "marginBottom": "16px",
            "borderLeft": f"4px solid {Styles.colorPalette[1]}",
        })

        # KPI row
        kpi_row = html.Div([
            Styles.kpiboxes(
                "Trade Value",
                f"{max(sell_value, buy_value):,.0f}",
                Styles.colorPalette[0],
            ),
            Styles.kpiboxes(
                "New Portfolio Value",
                f"{total_mv_after:,.0f}",
                Styles.colorPalette[1],
            ),
            Styles.kpiboxes(
                "Vol Change",
                f"{vol_change_pct:+.2f}%" if vol_change_pct is not None else "N/A",
                Styles.strongRed if (vol_change_pct or 0) > 0 else Styles.strongGreen,
            ),
            Styles.kpiboxes(
                "Dividend Income \u0394",
                f"{div_change:+,.0f}",
                Styles.strongGreen if div_change >= 0 else Styles.strongRed,
            ),
        ], className="kpi-row")

        # Allocation donut charts
        alloc_row = html.Div([
            html.Div(dcc.Graph(figure=donut_before, config={"displayModeBar": False}),
                     className="card", style={"flex": "1"}),
            html.Div(dcc.Graph(figure=donut_after, config={"displayModeBar": False}),
                     className="card", style={"flex": "1"}),
        ], className="grid-2")

        # Risk + Dividend + Concentration comparison bars
        comparison_data = []
        categories = []

        if vol_before is not None and vol_after is not None:
            categories.append("Volatility (%)")
            comparison_data.append((vol_before * 100, vol_after * 100))

        categories.append("Dividend Income")
        comparison_data.append((div_before, div_after))

        categories.append("HHI (x1000)")
        comparison_data.append((hhi_before * 1000, hhi_after * 1000))

        impact_chart = {
            "data": [
                {
                    "type": "bar",
                    "x": categories,
                    "y": [d[0] for d in comparison_data],
                    "name": "Before",
                    "marker": {"color": Styles.colorPalette[0]},
                    "text": [f"{d[0]:,.1f}" for d in comparison_data],
                    "textposition": "outside",
                },
                {
                    "type": "bar",
                    "x": categories,
                    "y": [d[1] for d in comparison_data],
                    "name": "After",
                    "marker": {"color": Styles.colorPalette[1]},
                    "text": [f"{d[1]:,.1f}" for d in comparison_data],
                    "textposition": "outside",
                },
            ],
            "layout": Styles.graph_layout(
                title="Impact Analysis: Before vs After",
                barmode="group",
                yaxis={"title": ""},
            ),
        }

        impact_row = html.Div(
            dcc.Graph(figure=impact_chart, config={"displayModeBar": False}),
            className="card",
        )

        return html.Div([
            trade_card,
            kpi_row,
            html.H5("Allocation Comparison", style={"marginTop": "16px"}),
            alloc_row,
            html.H5("Impact Analysis", style={"marginTop": "16px"}),
            impact_row,
        ])


def _error(msg: str):
    return html.Div(
        html.P(msg, style={"color": Styles.strongRed}),
        className="card", style={"padding": "16px"},
    )
