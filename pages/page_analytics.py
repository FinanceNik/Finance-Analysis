import numpy as np
import pandas as pd
from dash import dcc, html, Input, Output
import Styles
import config
import dataLoadPositions as dlp


def _compute_analytics():
    """Compute per-holding analytics and portfolio-level metrics."""
    df = dlp.add_position_pnl_columns()
    if df.empty:
        return df, {}

    total_mv = df["market_value"].sum()
    df["weight"] = df["market_value"] / total_mv

    # Try to load historical data for Sharpe ratio
    try:
        hist = pd.read_csv("data/historical_data.csv")
        if "date" in hist.columns:
            hist = hist.set_index("date")
        hist = 10 ** hist
        daily_returns = hist.pct_change().dropna()

        avg_annual_return = daily_returns.mean() * 252
        annual_vol = daily_returns.std() * np.sqrt(252)

        portfolio_return = avg_annual_return.mean()
        portfolio_vol = annual_vol.mean()
        portfolio_sharpe = ((portfolio_return - config.RISK_FREE_RATE) / portfolio_vol
                            if portfolio_vol > 0 else None)
    except Exception:
        portfolio_sharpe = None
        portfolio_return = None
        portfolio_vol = None

    metrics = {
        "sharpe": round(portfolio_sharpe, 2) if portfolio_sharpe is not None else "N/A",
        "annual_return": f"{portfolio_return * 100:.1f}%" if portfolio_return is not None else "N/A",
        "annual_vol": f"{portfolio_vol * 100:.1f}%" if portfolio_vol is not None else "N/A",
        "total_mv": int(total_mv),
    }

    return df, metrics


def _build_expense_ratio_section(df):
    """Build expense ratio analysis for ETFs."""
    if df.empty or "asset_type" not in df.columns:
        return html.Div()

    etfs = df[df["asset_type"].str.lower().isin(["etf", "etfs"])].copy()
    if etfs.empty:
        return html.Div()

    etfs["ter"] = etfs["symbol"].map(config.ETF_EXPENSE_RATIOS).fillna(0)
    etfs["annual_cost"] = etfs["market_value"] * etfs["ter"]

    total_etf_value = etfs["market_value"].sum()
    weighted_ter = (etfs["ter"] * etfs["market_value"]).sum() / total_etf_value if total_etf_value > 0 else 0
    total_annual_cost = etfs["annual_cost"].sum()

    etfs_with_ter = etfs[etfs["ter"] > 0].sort_values("annual_cost", ascending=True)

    if etfs_with_ter.empty:
        return html.Div()

    chart = {
        'data': [{
            'type': 'bar',
            'x': etfs_with_ter['annual_cost'].round(2).tolist(),
            'y': etfs_with_ter['symbol'].tolist(),
            'orientation': 'h',
            'marker': {'color': Styles.colorPalette[3]},
            'text': [f"{t:.2%} TER" for t in etfs_with_ter['ter']],
            'textposition': 'outside',
        }],
        'layout': {
            'title': f'ETF Annual Costs (Weighted TER: {weighted_ter:.2%}, Total: {total_annual_cost:,.0f}/yr)',
            'xaxis': {'title': 'Annual Cost'},
            'margin': {'t': 40, 'b': 40, 'l': 120, 'r': 80},
            'height': max(250, len(etfs_with_ter) * 35),
        }
    }

    return html.Div([
        html.Hr(),
        html.Div([
            dcc.Graph(id='expense-ratio-chart', figure=chart)
        ], style=Styles.STYLE(100)),
    ])


def _build_currency_impact(df):
    """Build currency exposure analysis."""
    if df.empty or "currency" not in df.columns:
        return html.Div()

    total_mv = df["market_value"].sum()
    ccy_grouped = df.groupby("currency").agg(
        value=("market_value", "sum"),
        cost=("cost_basis", "sum"),
        pnl=("unrealized_pnl", "sum"),
    ).reset_index()
    ccy_grouped["weight"] = ccy_grouped["value"] / total_mv
    ccy_grouped["pnl_pct"] = ccy_grouped["pnl"] / ccy_grouped["cost"].replace(0, np.nan)

    colors = [Styles.strongGreen if v >= 0 else Styles.strongRed for v in ccy_grouped["pnl"]]

    chart = {
        'data': [
            {
                'type': 'bar',
                'x': ccy_grouped['currency'].tolist(),
                'y': ccy_grouped['value'].round(0).tolist(),
                'name': 'Market Value',
                'marker': {'color': Styles.colorPalette[0]},
            },
            {
                'type': 'bar',
                'x': ccy_grouped['currency'].tolist(),
                'y': ccy_grouped['pnl'].round(0).tolist(),
                'name': 'Unrealized P&L',
                'marker': {'color': colors},
            },
        ],
        'layout': {
            'title': 'Performance by Currency',
            'barmode': 'group',
            'xaxis': {'title': 'Currency'},
            'yaxis': {'title': 'Value'},
            'margin': {'t': 40, 'b': 40, 'l': 60, 'r': 40},
        }
    }

    return html.Div([
        dcc.Graph(id='currency-impact-chart', figure=chart)
    ], style=Styles.STYLE(48))


def _build_benchmark_section():
    """Build benchmark comparison chart."""
    try:
        hist = pd.read_csv("data/historical_data.csv")
        if "date" in hist.columns:
            hist = hist.set_index("date")
        hist = 10 ** hist
    except Exception:
        return html.Div()

    if hist.empty or hist.shape[1] < 2:
        return html.Div()

    # Normalize all to 100 at start
    first_valid = hist.apply(lambda s: s.dropna().iloc[0] if not s.dropna().empty else np.nan)
    normalized = (hist / first_valid) * 100

    # Portfolio average (equal weight across all tickers)
    portfolio_avg = normalized.mean(axis=1).dropna()

    traces = [{
        'x': portfolio_avg.index.tolist(),
        'y': portfolio_avg.round(2).tolist(),
        'type': 'scatter',
        'mode': 'lines',
        'name': 'Portfolio (Equal Weight)',
        'line': {'color': Styles.colorPalette[0], 'width': 3},
    }]

    # Add individual tickers in lighter colors
    for col in normalized.columns:
        series = normalized[col].dropna()
        if not series.empty:
            traces.append({
                'x': series.index.tolist(),
                'y': series.round(2).tolist(),
                'type': 'scatter',
                'mode': 'lines',
                'name': col,
                'line': {'width': 1},
                'opacity': 0.5,
            })

    chart = {
        'data': traces,
        'layout': {
            'title': 'Normalized Performance (Base = 100)',
            'xaxis': {'title': 'Date', 'type': 'date'},
            'yaxis': {'title': 'Indexed Value'},
            'margin': {'t': 40, 'b': 40, 'l': 60, 'r': 40},
            'hovermode': 'x unified',
        }
    }

    return html.Div([
        dcc.Graph(id='benchmark-chart', figure=chart)
    ], style=Styles.STYLE(100))


def layout():
    df, metrics = _compute_analytics()

    if df.empty:
        return html.Div([
            html.Hr(),
            html.H4("No portfolio data available."),
        ])

    # --- KPI row ---
    kpi_row = html.Div([
        Styles.kpiboxes('Portfolio Sharpe:', metrics.get("sharpe", "N/A"), Styles.colorPalette[0]),
        Styles.kpiboxes('Est. Annual Return:', metrics.get("annual_return", "N/A"), Styles.colorPalette[1]),
        Styles.kpiboxes('Est. Annual Vol:', metrics.get("annual_vol", "N/A"), Styles.colorPalette[2]),
        Styles.kpiboxes('Total Market Value:', f"{metrics.get('total_mv', 0):,}", Styles.colorPalette[3]),
    ])

    # --- Per-holding P&L chart ---
    df_sorted = df.sort_values("unrealized_pnl", ascending=True)
    colors = [Styles.strongGreen if v >= 0 else Styles.strongRed for v in df_sorted["unrealized_pnl"]]

    pnl_chart = {
        'data': [{
            'type': 'bar',
            'x': df_sorted['unrealized_pnl'].tolist(),
            'y': df_sorted['symbol'].tolist() if 'symbol' in df_sorted.columns else df_sorted.index.tolist(),
            'orientation': 'h',
            'marker': {'color': colors},
        }],
        'layout': {
            'title': 'Unrealized P&L by Holding',
            'xaxis': {'title': 'Unrealized P&L'},
            'margin': {'t': 40, 'b': 40, 'l': 120, 'r': 40},
            'height': max(300, len(df_sorted) * 28),
        }
    }

    # --- Per-holding return % chart ---
    df_pct = df.dropna(subset=["pnl_pct"]).sort_values("pnl_pct", ascending=True)
    pct_colors = [Styles.strongGreen if v >= 0 else Styles.strongRed for v in df_pct["pnl_pct"]]

    return_chart = {
        'data': [{
            'type': 'bar',
            'x': (df_pct['pnl_pct'] * 100).round(1).tolist(),
            'y': df_pct['symbol'].tolist() if 'symbol' in df_pct.columns else df_pct.index.tolist(),
            'orientation': 'h',
            'marker': {'color': pct_colors},
            'text': [f"{v:.1f}%" for v in (df_pct['pnl_pct'] * 100)],
            'textposition': 'outside',
        }],
        'layout': {
            'title': 'Return % by Holding',
            'xaxis': {'title': 'Return (%)'},
            'margin': {'t': 40, 'b': 40, 'l': 120, 'r': 60},
            'height': max(300, len(df_pct) * 28),
        }
    }

    # --- Top holdings by weight ---
    df_top = df.nlargest(10, "weight")
    weight_chart = {
        'data': [{
            'type': 'bar',
            'x': df_top['symbol'].tolist() if 'symbol' in df_top.columns else df_top.index.tolist(),
            'y': (df_top['weight'] * 100).round(1).tolist(),
            'marker': {'color': Styles.colorPalette[0]},
            'text': [f"{v:.1f}%" for v in (df_top['weight'] * 100)],
            'textposition': 'outside',
        }],
        'layout': {
            'title': 'Top 10 Holdings by Portfolio Weight',
            'yaxis': {'title': 'Weight (%)'},
            'margin': {'t': 40, 'b': 80, 'l': 40, 'r': 40},
        }
    }

    return html.Div([
        html.Hr(),
        html.H4("Portfolio Analytics"),
        kpi_row,
        html.Hr(),

        # Benchmark comparison
        _build_benchmark_section(),
        html.Hr(),

        # Top holdings
        html.Div([
            dcc.Graph(id='top-holdings-chart', figure=weight_chart)
        ], style=Styles.STYLE(100)),
        html.Hr(),

        # P&L charts
        html.Div([
            dcc.Graph(id='pnl-by-holding-chart', figure=pnl_chart)
        ], style=Styles.STYLE(48)),
        html.Div([''], style=Styles.FILLER()),
        html.Div([
            dcc.Graph(id='return-by-holding-chart', figure=return_chart)
        ], style=Styles.STYLE(48)),
        html.Hr(),

        # Currency impact
        html.Div([
            _build_currency_impact(df),
            html.Div([''], style=Styles.FILLER()),
        ]),

        # Expense ratio tracking
        _build_expense_ratio_section(df),
    ])
