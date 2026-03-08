import numpy as np
import pandas as pd
from dash import dcc, html
import Styles
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
        # Convert from log scale back to price
        hist = 10 ** hist
        daily_returns = hist.pct_change().dropna()

        avg_annual_return = daily_returns.mean() * 252
        annual_vol = daily_returns.std() * np.sqrt(252)
        risk_free_rate = 0.02

        sharpe_per_ticker = (avg_annual_return - risk_free_rate) / annual_vol.replace(0, np.nan)
        portfolio_return = avg_annual_return.mean()
        portfolio_vol = annual_vol.mean()
        portfolio_sharpe = (portfolio_return - risk_free_rate) / portfolio_vol if portfolio_vol > 0 else 0
    except (FileNotFoundError, Exception):
        sharpe_per_ticker = pd.Series(dtype=float)
        portfolio_sharpe = 0
        portfolio_return = 0
        portfolio_vol = 0

    metrics = {
        "sharpe": round(portfolio_sharpe, 2),
        "annual_return": round(portfolio_return * 100, 1),
        "annual_vol": round(portfolio_vol * 100, 1),
        "total_mv": int(total_mv),
    }

    return df, metrics


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
        Styles.kpiboxes('Est. Annual Return:', f"{metrics.get('annual_return', 0)}%", Styles.colorPalette[1]),
        Styles.kpiboxes('Est. Annual Vol:', f"{metrics.get('annual_vol', 0)}%", Styles.colorPalette[2]),
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

        html.Div([
            dcc.Graph(id='top-holdings-chart', figure=weight_chart)
        ], style=Styles.STYLE(100)),
        html.Hr(),

        html.Div([
            dcc.Graph(id='pnl-by-holding-chart', figure=pnl_chart)
        ], style=Styles.STYLE(48)),
        html.Div([''], style=Styles.FILLER()),
        html.Div([
            dcc.Graph(id='return-by-holding-chart', figure=return_chart)
        ], style=Styles.STYLE(48)),
    ])
