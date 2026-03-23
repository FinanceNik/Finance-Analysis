import numpy as np
import pandas as pd
from dash import dcc, html
import yfinance as yf
import Styles
import config
import dataLoadPositions as dlp
import dataLoadTransactions as dlt
import user_settings
from utils import load_symbol_mapping

def _fmt_currency(value):
    """Format a numeric value as a readable currency string."""
    if value is None:
        return "N/A"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.1f}M"
    return f"{value:,.0f}"

def _safe_div(numerator, denominator, default=0):
    """Safe division that returns default on zero/None denominator."""
    if not denominator:
        return default
    return numerator / denominator

def _build_allocation_donut():
    """Build a small donut chart of portfolio allocation by asset type."""
    alloc = dlp.allocation_by_asset_type()
    if alloc.empty:
        return {
            'data': [],
            'layout': Styles.graph_layout(
                title='Portfolio Allocation',
                annotations=[{
                    'text': 'No data', 'showarrow': False,
                    'font': {'size': 14}
                }],
            ),
        }

    return {
        'data': [{
            'type': 'pie',
            'labels': alloc['asset_type'].tolist(),
            'values': alloc['weight'].tolist(),
            'hole': 0.55,
            'textinfo': 'label+percent',
            'hoverinfo': 'label+value+percent',
            'marker': {'colors': Styles.purple_list[:len(alloc)]},
        }],
        'layout': Styles.graph_layout(
            title='Portfolio Allocation',
            showlegend=False,
            margin={'t': 40, 'b': 20, 'l': 20, 'r': 20},
        ),
    }

def _build_dividend_sparkline():
    """Build a sparkline-style bar chart showing last 12 months of dividends."""
    try:
        months, vals_2y, vals_prev, vals_current = dlt.monthly_totals("Dividend")
    except Exception:
        months, vals_prev, vals_current = [], [], []

    if not months:
        return {
            'data': [],
            'layout': Styles.graph_layout(
                title='Monthly Dividends',
                annotations=[{
                    'text': 'No data', 'showarrow': False,
                    'font': {'size': 14}
                }],
            ),
        }

    # Normalize to positive values (dividends may be stored as negative)
    vals_prev = [abs(v) for v in vals_prev]
    vals_current = [abs(v) for v in vals_current]

    return {
        'data': [
            {
                'type': 'bar',
                'x': months,
                'y': vals_prev,
                'name': str(dlt.currentYear - 1),
                'marker': {'color': Styles.colorPalette[2], 'opacity': 0.4},
            },
            {
                'type': 'bar',
                'x': months,
                'y': vals_current,
                'name': str(dlt.currentYear),
                'marker': {'color': Styles.strongGreen},
            },
        ],
        'layout': Styles.graph_layout(
            title='Monthly Dividends',
            barmode='group',
            showlegend=True,
            legend={'orientation': 'h', 'y': -0.15, 'x': 0.5, 'xanchor': 'center'},
            margin={'t': 40, 'b': 50, 'l': 50, 'r': 20},
            xaxis={'tickangle': -45},
            yaxis={'title': ''},
        ),
    }

def _build_top_movers():
    """Build a horizontal bar chart showing top 5 gainers and losers by unrealized PnL."""
    df = dlp.add_position_pnl_columns()
    if df.empty or 'unrealized_pnl' not in df.columns:
        return {
            'data': [],
            'layout': Styles.graph_layout(
                title='Top Movers',
                annotations=[{
                    'text': 'No data', 'showarrow': False,
                    'font': {'size': 14}
                }],
            ),
        }

    df = df.dropna(subset=['unrealized_pnl'])
    symbol_col = 'symbol' if 'symbol' in df.columns else df.index

    # Top 5 gainers and top 5 losers
    top_gainers = df.nlargest(5, 'unrealized_pnl')
    top_losers = df.nsmallest(5, 'unrealized_pnl')

    # Combine and sort for display
    movers = pd.concat([top_losers, top_gainers]).drop_duplicates()
    movers = movers.sort_values('unrealized_pnl', ascending=True)

    symbols = movers['symbol'].tolist() if 'symbol' in movers.columns else movers.index.tolist()
    pnl_values = movers['unrealized_pnl'].tolist()
    colors = [Styles.strongGreen if v >= 0 else Styles.strongRed for v in pnl_values]

    return {
        'data': [{
            'type': 'bar',
            'x': pnl_values,
            'y': symbols,
            'orientation': 'h',
            'marker': {'color': colors},
            'text': [f"{v:+,.0f}" for v in pnl_values],
            'textposition': 'outside',
        }],
        'layout': Styles.graph_layout(
            title='Top Movers (Unrealized P&L)',
            margin={'t': 40, 'b': 30, 'l': 100, 'r': 60},
            xaxis={'title': ''},
            yaxis={'title': ''},
        ),
    }

def _build_fire_progress():
    """Build FIRE progress metric with a visual progress bar."""
    saved = user_settings.get("budget", {}) or {}
    exp = saved.get("expenses", {}) or {}

    monthly_expenses = sum(v for v in exp.values() if isinstance(v, (int, float)))
    annual_expenses = monthly_expenses * 12

    fire_number = annual_expenses / config.FIRE_WITHDRAWAL_RATE if annual_expenses > 0 else 0
    portfolio = dlp.portfolio_total_value()
    progress = _safe_div(portfolio, fire_number, 0) if fire_number > 0 else 0
    progress_pct = min(progress * 100, 100)

    bar_color = Styles.strongGreen if progress >= 1.0 else Styles.colorPalette[0]

    return html.Div([
        html.H5("FIRE Progress", style={"margin": "0 0 10px 0"}),
        html.Div([
            html.Span(f"{progress:.1%}", style={
                "fontSize": "36px", "fontWeight": "bold",
                "color": bar_color,
            }),
            html.Span(" of FIRE number", style={
                "fontSize": "14px", "color": "var(--text-muted, #888)", "marginLeft": "8px",
            }),
        ]),
        html.Div([
            html.Div(style={
                "width": f"{progress_pct:.0f}%",
                "height": "16px",
                "backgroundColor": bar_color,
                "borderRadius": "8px",
                "transition": "width 0.5s ease",
            }),
        ], style={
            "width": "100%", "height": "16px",
            "backgroundColor": "var(--progress-bg, #e0e0e0)",
            "borderRadius": "8px", "marginTop": "12px",
        }),
        html.Div([
            html.Div([
                html.Span("Portfolio: ", style={"color": "var(--text-muted, #888)", "fontSize": "13px"}),
                html.Span(f"{_fmt_currency(portfolio)}", style={"fontWeight": "bold", "fontSize": "13px"}),
            ], style={"marginTop": "10px"}),
            html.Div([
                html.Span("FIRE Number: ", style={"color": "var(--text-muted, #888)", "fontSize": "13px"}),
                html.Span(
                    f"{_fmt_currency(fire_number)}" if fire_number > 0 else "Set expenses in Budget",
                    style={"fontWeight": "bold", "fontSize": "13px"},
                ),
            ]),
        ]),
    ], style={"padding": "10px"})

def _build_performance_chart():
    """Build a normalized performance chart from historical_data.csv."""
    hist = dlp.load_historical_data()
    if hist.empty:
        return {
            'data': [],
            'layout': Styles.graph_layout(
                title='Performance Overview',
                annotations=[{
                    'text': 'No historical data available',
                    'showarrow': False, 'font': {'size': 14}
                }],
            ),
        }

    # Reset index so 'date' is a column (load_historical_data uses index_col=0)
    hist = hist.reset_index()

    if hist.empty:
        return {
            'data': [],
            'layout': Styles.graph_layout(title='Performance Overview'),
        }

    if "date" in hist.columns:
        data_cols = [c for c in hist.columns if c != "date"]
    else:
        data_cols = list(hist.columns)

    price_data = hist[data_cols]

    # Consolidate duplicate dates from outer-joined exchanges
    if "date" in hist.columns:
        price_data.index = hist["date"]
        price_data = price_data.groupby(price_data.index).first()
        price_data = price_data.sort_index().ffill()
        dates = price_data.index.tolist()
    else:
        dates = hist.index.tolist()

    # Build symbol mapping: broker symbol -> Yahoo ticker and reverse
    sym_to_ticker = load_symbol_mapping()
    ticker_to_sym = {v: k for k, v in sym_to_ticker.items() if v}

    # Separate benchmark columns from portfolio holdings
    bench_tickers = config.BENCHMARK_TICKERS
    holding_cols = [c for c in data_cols if c not in bench_tickers]
    bench_cols = [c for c in bench_tickers if c in data_cols]

    # Normalize to 100 at the first valid value for each series
    first_valid = price_data.apply(lambda s: s.dropna().iloc[0] if not s.dropna().empty else np.nan)
    normalized = (price_data / first_valid) * 100

    # Portfolio average from holdings only (exclude benchmarks)
    if holding_cols:
        portfolio_avg = normalized[holding_cols].mean(axis=1).dropna()
    else:
        portfolio_avg = normalized.mean(axis=1).dropna()

    traces = [{
        'x': dates,
        'y': portfolio_avg.round(2).tolist(),
        'type': 'scatter',
        'mode': 'lines',
        'name': 'Portfolio',
        'line': {'color': Styles.colorPalette[0], 'width': 3},
    }]

    # Benchmark overlays
    bench_colors = [Styles.colorPalette[2], Styles.strongGreen]
    for i, col in enumerate(bench_cols):
        series = normalized[col].dropna()
        if not series.empty:
            label = config.BENCHMARK_NAMES.get(col, col)
            x_vals = [dates[j] for j in series.index] if isinstance(series.index[0], int) else series.index.tolist()
            traces.append({
                'x': x_vals,
                'y': series.round(2).tolist(),
                'type': 'scatter',
                'mode': 'lines',
                'name': label,
                'line': {'color': bench_colors[i % len(bench_colors)],
                         'width': 2, 'dash': 'dash'},
            })

    # Blended benchmark overlay
    try:
        blend_cfg = config.BLENDED_BENCHMARK
        if blend_cfg and dates:
            start_date = str(dates[0])[:10] if dates else None
            if start_date:
                blend_tickers = list(blend_cfg.keys())
                blend_data = yf.download(blend_tickers, start=start_date, auto_adjust=True)
                if not blend_data.empty:
                    # Extract 'Close' prices; handle single vs multi-ticker
                    if len(blend_tickers) == 1:
                        close = blend_data[['Close']].copy()
                        close.columns = blend_tickers
                    else:
                        close = blend_data['Close']
                    close = close.sort_index().ffill()
                    # Normalize each component to 100 at its first valid value
                    first_vals = close.apply(lambda s: s.dropna().iloc[0] if not s.dropna().empty else np.nan)
                    norm_blend = (close / first_vals) * 100
                    # Compute weighted blend
                    blended = pd.Series(0.0, index=norm_blend.index)
                    for tkr, weight in blend_cfg.items():
                        if tkr in norm_blend.columns:
                            blended += norm_blend[tkr].fillna(method='ffill').fillna(100) * weight
                    blended = blended.dropna()
                    if not blended.empty:
                        traces.append({
                            'x': blended.index.strftime('%Y-%m-%d').tolist(),
                            'y': blended.round(2).tolist(),
                            'type': 'scatter',
                            'mode': 'lines',
                            'name': config.BLENDED_BENCHMARK_NAME,
                            'line': {'color': '#FF9500', 'width': 2.5, 'dash': 'dashdot'},
                        })
    except Exception:
        pass  # Blended benchmark is best-effort; don't break the chart

    # Individual holdings as faint lines
    for col in holding_cols:
        series = normalized[col].dropna()
        if not series.empty:
            x_vals = [dates[j] for j in series.index] if isinstance(series.index[0], int) else series.index.tolist()
            display_name = ticker_to_sym.get(col, col)
            traces.append({
                'x': x_vals,
                'y': series.round(2).tolist(),
                'type': 'scatter',
                'mode': 'lines',
                'name': display_name,
                'line': {'width': 1},
                'opacity': 0.35,
            })

    return {
        'data': traces,
        'layout': Styles.graph_layout(
            title='Portfolio vs Benchmarks (Normalized to 100)',
            xaxis={'title': 'Date', 'type': 'date' if 'date' in hist.columns else 'linear'},
            yaxis={'title': 'Indexed Value'},
            hovermode='x unified',
            legend={'orientation': 'h', 'y': -0.15, 'x': 0.5, 'xanchor': 'center'},
            margin={'t': 40, 'b': 60, 'l': 50, 'r': 30},
        ),
    }

def _get_portfolio_sparkline():
    """Get last 30 data points from historical data for a portfolio sparkline."""
    try:
        hist = dlp.load_historical_data()
        if hist.empty:
            return None
        hist = hist.reset_index()
        data_cols = [c for c in hist.columns if c != "date"]
        prices = hist[data_cols]
        # Consolidate duplicate dates from outer-joined exchanges
        if "date" in hist.columns:
            prices.index = hist["date"]
            prices = prices.groupby(prices.index).first()
            prices = prices.sort_index().ffill()
        avg = prices.mean(axis=1).dropna()
        points = avg.tail(30).tolist()
        return points if len(points) >= 2 else None
    except Exception:
        return None

def _get_dividend_sparkline():
    """Get monthly dividend totals for sparkline."""
    try:
        _, _, _, vals = dlt.monthly_totals("Dividend")
        vals = [abs(v) for v in vals]  # Normalize to positive
        return vals if len(vals) >= 2 else None
    except Exception:
        return None

def layout():
    # ── Gather summary data ──
    portfolio_value = dlp.portfolio_total_value()
    return_pct = dlp.portfolio_return_pct()

    # Net worth from settings + portfolio
    nw_data = user_settings.get("networth", {}) or {}
    if isinstance(nw_data, dict):
        assets = sum(v for k, v in nw_data.items()
                     if isinstance(v, (int, float)) and k != "liabilities")
        liabilities = nw_data.get("liabilities", 0) or 0
        saved_networth = assets - liabilities
    else:
        saved_networth = nw_data if isinstance(nw_data, (int, float)) else 0
    net_worth = saved_networth + portfolio_value

    # Monthly savings from budget settings
    saved_budget = user_settings.get("budget", {}) or {}
    inc = saved_budget.get("income", {}) or {}
    exp = saved_budget.get("expenses", {}) or {}
    total_income = sum(v for v in inc.values() if isinstance(v, (int, float)))
    total_expenses = sum(v for v in exp.values() if isinstance(v, (int, float)))
    monthly_savings = total_income - total_expenses

    # Color for return / savings
    return_color = Styles.strongGreen if return_pct >= 0 else Styles.strongRed
    savings_color = Styles.strongGreen if monthly_savings >= 0 else Styles.strongRed

    # Sparkline data
    portfolio_spark = _get_portfolio_sparkline()
    dividend_spark = _get_dividend_sparkline()

    return html.Div([
        dcc.Loading(type="circle", children=[

            # ── Row 1: Hero KPIs ──
            html.Div([
                Styles.kpiboxes_spark("Net Worth", _fmt_currency(net_worth), Styles.colorPalette[0]),
                Styles.kpiboxes_spark("Portfolio Value", _fmt_currency(portfolio_value), Styles.colorPalette[1], portfolio_spark),
                Styles.kpiboxes_spark("YTD Return", f"{return_pct:.1%}", return_color),
                Styles.kpiboxes_spark("Monthly Savings", _fmt_currency(monthly_savings), savings_color, dividend_spark),
            ], className="kpi-row"),

            # ── Row 2: Allocation donut + Dividend sparkline ──
            html.Div([
                html.Div([
                    dcc.Graph(
                        id='dash-allocation-donut',
                        figure=_build_allocation_donut(),
                        config={'displayModeBar': False},
                    ),
                ], className="card"),
                html.Div([
                    dcc.Graph(
                        id='dash-dividend-sparkline',
                        figure=_build_dividend_sparkline(),
                        config={'displayModeBar': False},
                    ),
                ], className="card"),
            ], className="grid-2"),

            # ── Row 3: Top Movers + FIRE Progress ──
            html.Div([
                html.Div([
                    dcc.Graph(
                        id='dash-top-movers',
                        figure=_build_top_movers(),
                        config={'displayModeBar': False},
                    ),
                ], className="card"),
                html.Div([
                    _build_fire_progress(),
                ], className="card"),
            ], className="grid-2"),

            # ── Row 4: Performance Overview (full width) ──
            html.Div([
                dcc.Graph(
                    id='dash-performance-chart',
                    figure=_build_performance_chart(),
                ),
            ], className="card"),

        ]),
    ])
