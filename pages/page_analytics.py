import numpy as np
import pandas as pd
from dash import dcc, html, Input, Output
from datetime import datetime
import Styles
import config
import dataLoadPositions as dlp
import dataLoadTransactions as dlt


def _compute_analytics():
    """Compute per-holding analytics and portfolio-level metrics."""
    df = dlp.add_position_pnl_columns()
    if df.empty:
        return df, {}, pd.DataFrame()

    total_mv = df["market_value"].sum()
    df["weight"] = df["market_value"] / total_mv

    # --- Historical data for Sharpe, Sortino, and Drawdown ---
    portfolio_sharpe = None
    portfolio_return = None
    portfolio_vol = None
    sortino_ratio = None
    max_drawdown = None
    drawdown_series = pd.DataFrame()

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

        # --- Sortino Ratio ---
        try:
            portfolio_daily = daily_returns.mean(axis=1)
            negative_returns = portfolio_daily[portfolio_daily < 0]
            if len(negative_returns) > 1:
                downside_deviation = negative_returns.std() * np.sqrt(252)
                if downside_deviation > 0:
                    sortino_ratio = (portfolio_return - config.RISK_FREE_RATE) / downside_deviation
        except Exception:
            sortino_ratio = None

        # --- Max Drawdown from portfolio average ---
        try:
            portfolio_avg = hist.mean(axis=1).dropna()
            running_max = portfolio_avg.cummax()
            drawdown = (portfolio_avg - running_max) / running_max
            max_drawdown = drawdown.min()
            # Build drawdown series for chart
            drawdown_series = pd.DataFrame({
                "date": drawdown.index,
                "drawdown": (drawdown * 100).values,
            })
        except Exception:
            max_drawdown = None
            drawdown_series = pd.DataFrame()
    except Exception:
        pass

    # --- CAGR from transaction history ---
    cagr = None
    try:
        txn_df = dlt.ingest_transactions()
        if not txn_df.empty and "date" in txn_df.columns and "transaction" in txn_df.columns:
            buys = txn_df[txn_df["transaction"].str.lower() == "buy"]
            if not buys.empty:
                first_buy_date = buys["date"].min()
                today = datetime.today()
                years = (today - first_buy_date).days / 365.25
                current_value = dlp.portfolio_total_value()
                total_invested = dlp.portfolio_cost_basis()
                if years > 0 and total_invested > 0 and current_value > 0:
                    cagr = (current_value / total_invested) ** (1 / years) - 1
    except Exception:
        cagr = None

    # --- Concentration Risk (Herfindahl Index) ---
    hhi = None
    effective_positions = None
    try:
        weights = df["weight"].values
        hhi = float(np.sum(weights ** 2))
        if hhi > 0:
            effective_positions = 1.0 / hhi
    except Exception:
        hhi = None
        effective_positions = None

    # --- Dividend Growth Rate (YoY) ---
    div_growth = None
    try:
        current_year = datetime.today().year
        div_this_year = dlt.total_transaction_amount(current_year, "Dividend")
        div_last_year = dlt.total_transaction_amount(current_year - 1, "Dividend")
        # Annualize current year dividends if not full year yet
        today = datetime.today()
        day_of_year = today.timetuple().tm_yday
        days_in_year = 366 if (current_year % 4 == 0 and (current_year % 100 != 0 or current_year % 400 == 0)) else 365
        if day_of_year > 30 and div_this_year != 0:
            annualized_this_year = div_this_year * (days_in_year / day_of_year)
        else:
            annualized_this_year = div_this_year
        if div_last_year != 0 and abs(div_last_year) > 0:
            div_growth = (annualized_this_year / div_last_year - 1) * 100
    except Exception:
        div_growth = None

    metrics = {
        "sharpe": round(portfolio_sharpe, 2) if portfolio_sharpe is not None else "N/A",
        "annual_return": f"{portfolio_return * 100:.1f}%" if portfolio_return is not None else "N/A",
        "annual_vol": f"{portfolio_vol * 100:.1f}%" if portfolio_vol is not None else "N/A",
        "total_mv": int(total_mv),
        # New KPIs
        "cagr": f"{cagr * 100:.1f}%" if cagr is not None else "N/A",
        "max_drawdown": f"{max_drawdown * 100:.1f}%" if max_drawdown is not None else "N/A",
        "sortino": round(sortino_ratio, 2) if sortino_ratio is not None else "N/A",
        "concentration": (
            f"{hhi:.2f} ({effective_positions:.0f} eff. pos.)"
            if hhi is not None and effective_positions is not None
            else "N/A"
        ),
        "div_growth": f"{div_growth:+.1f}%" if div_growth is not None else "N/A",
    }

    return df, metrics, drawdown_series


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
            **Styles.graph_layout(
                title=f'ETF Annual Costs (Weighted TER: {weighted_ter:.2%}, Total: {total_annual_cost:,.0f}/yr)',
                xaxis={'title': 'Annual Cost'},
                margin={'t': 40, 'b': 40, 'l': 120, 'r': 80},
            ),
            'height': max(250, len(etfs_with_ter) * 35),
        }
    }

    return html.Div([
        html.Hr(),
        html.Div([
            dcc.Graph(id='expense-ratio-chart', figure=chart)
        ], className="card", style=Styles.STYLE(100)),
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
        'layout': Styles.graph_layout(
            title='Performance by Currency',
            barmode='group',
            xaxis={'title': 'Currency'},
            yaxis={'title': 'Value'},
        ),
    }

    return html.Div([
        dcc.Graph(id='currency-impact-chart', figure=chart)
    ], className="card", style=Styles.STYLE(48))


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
        'layout': Styles.graph_layout(
            title='Normalized Performance (Base = 100)',
            xaxis={'title': 'Date', 'type': 'date'},
            yaxis={'title': 'Indexed Value'},
            hovermode='x unified',
        ),
    }

    return html.Div([
        dcc.Graph(id='benchmark-chart', figure=chart)
    ], className="card", style=Styles.STYLE(100))


def _build_drawdown_chart(drawdown_series):
    """Build a filled area chart showing portfolio drawdown over time."""
    if drawdown_series.empty:
        return html.Div()

    chart = {
        'data': [{
            'type': 'scatter',
            'x': drawdown_series['date'].tolist(),
            'y': drawdown_series['drawdown'].round(2).tolist(),
            'mode': 'lines',
            'fill': 'tozeroy',
            'fillcolor': 'rgba(255, 59, 48, 0.3)',
            'line': {'color': Styles.strongRed, 'width': 1.5},
            'name': 'Drawdown',
            'hovertemplate': '%{x}<br>Drawdown: %{y:.2f}%<extra></extra>',
        }],
        'layout': Styles.graph_layout(
            title='Portfolio Drawdown Over Time',
            xaxis={'title': 'Date', 'type': 'date'},
            yaxis={'title': 'Drawdown (%)', 'ticksuffix': '%'},
            hovermode='x unified',
        ),
    }

    return html.Div([
        dcc.Graph(id='drawdown-chart', figure=chart)
    ], className="card", style=Styles.STYLE(100))


def _build_correlation_heatmap():
    """Build a correlation matrix heatmap from historical returns."""
    try:
        hist = pd.read_csv("data/historical_data.csv")
        if "date" in hist.columns:
            hist = hist.set_index("date")
        hist = 10 ** hist
        daily_returns = hist.pct_change().dropna()
        corr = daily_returns.corr()
    except Exception:
        return html.Div()

    if corr.empty:
        return html.Div()

    chart = {
        'data': [{
            'type': 'heatmap',
            'z': corr.values.round(2).tolist(),
            'x': corr.columns.tolist(),
            'y': corr.index.tolist(),
            'colorscale': 'RdBu_r',
            'zmin': -1, 'zmax': 1,
            'text': [[f"{v:.2f}" for v in row] for row in corr.values],
            'texttemplate': '%{text}',
            'hovertemplate': '%{x} vs %{y}: %{z:.2f}<extra></extra>',
            'colorbar': {'title': 'Corr'},
        }],
        'layout': Styles.graph_layout(
            title='Return Correlation Matrix',
            height=max(400, len(corr) * 45),
            margin={'l': 100, 'b': 100, 't': 40, 'r': 20},
        ),
    }

    return html.Div([
        dcc.Graph(id='correlation-heatmap', figure=chart)
    ], className="card", style=Styles.STYLE(100))


def _build_sector_treemap(df):
    """Build a treemap showing portfolio allocation by sector."""
    if df.empty or 'market_value' not in df.columns:
        return html.Div()

    df = df.copy()
    df["sector"] = df["symbol"].map(config.SECTOR_MAP).fillna("Other")

    labels = ["Portfolio"] + df["sector"].unique().tolist() + df["symbol"].tolist()
    parents = [""] + ["Portfolio"] * df["sector"].nunique() + df["sector"].tolist()
    values = [0] + [0] * df["sector"].nunique() + df["market_value"].round(0).tolist()

    chart = {
        'data': [{
            'type': 'treemap',
            'labels': labels,
            'parents': parents,
            'values': values,
            'textinfo': 'label+percent parent',
            'branchvalues': 'total',
            'marker': {'colorscale': 'Blues'},
        }],
        'layout': Styles.graph_layout(
            title='Sector Allocation (Treemap)',
            margin={'t': 40, 'b': 10, 'l': 10, 'r': 10},
            height=450,
        ),
    }

    return html.Div([
        dcc.Graph(id='sector-treemap', figure=chart)
    ], className="card", style=Styles.STYLE(48))


def _build_geography_treemap(df):
    """Build a treemap showing portfolio allocation by geography."""
    if df.empty or 'geography' not in df.columns or 'market_value' not in df.columns:
        return html.Div()

    df = df.copy()

    labels = ["Portfolio"] + df["geography"].unique().tolist() + df["symbol"].tolist()
    parents = [""] + ["Portfolio"] * df["geography"].nunique() + df["geography"].tolist()
    values = [0] + [0] * df["geography"].nunique() + df["market_value"].round(0).tolist()

    chart = {
        'data': [{
            'type': 'treemap',
            'labels': labels,
            'parents': parents,
            'values': values,
            'textinfo': 'label+percent parent',
            'branchvalues': 'total',
            'marker': {'colorscale': 'Greens'},
        }],
        'layout': Styles.graph_layout(
            title='Geography Allocation (Treemap)',
            margin={'t': 40, 'b': 10, 'l': 10, 'r': 10},
            height=450,
        ),
    }

    return html.Div([
        dcc.Graph(id='geo-treemap', figure=chart)
    ], className="card", style=Styles.STYLE(48))


def layout():
    df, metrics, drawdown_series = _compute_analytics()

    if df.empty:
        return html.Div([
            html.Hr(),
            html.H4("No portfolio data available."),
        ])

    # --- KPI row 1 (existing) ---
    kpi_row = html.Div([
        Styles.kpiboxes('Portfolio Sharpe', metrics.get("sharpe", "N/A"), Styles.colorPalette[0]),
        Styles.kpiboxes('Est. Annual Return', metrics.get("annual_return", "N/A"), Styles.colorPalette[1]),
        Styles.kpiboxes('Est. Annual Vol', metrics.get("annual_vol", "N/A"), Styles.colorPalette[2]),
        Styles.kpiboxes('Total Market Value', f"{metrics.get('total_mv', 0):,}", Styles.colorPalette[3]),
    ])

    # --- KPI row 2 (advanced metrics) ---
    kpi_row_2 = html.Div([
        Styles.kpiboxes('CAGR', metrics.get("cagr", "N/A"), Styles.colorPalette[0]),
        Styles.kpiboxes('Max Drawdown', metrics.get("max_drawdown", "N/A"), Styles.colorPalette[1]),
        Styles.kpiboxes('Sortino Ratio', metrics.get("sortino", "N/A"), Styles.colorPalette[2]),
        Styles.kpiboxes('Concentration', metrics.get("concentration", "N/A"), Styles.colorPalette[3]),
        Styles.kpiboxes('Dividend Growth', metrics.get("div_growth", "N/A"), Styles.colorPalette[0]),
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
            **Styles.graph_layout(
                title='Unrealized P&L by Holding',
                xaxis={'title': 'Unrealized P&L'},
                margin={'t': 40, 'b': 40, 'l': 120, 'r': 40},
            ),
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
            **Styles.graph_layout(
                title='Return % by Holding',
                xaxis={'title': 'Return (%)'},
                margin={'t': 40, 'b': 40, 'l': 120, 'r': 60},
            ),
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
        'layout': Styles.graph_layout(
            title='Top 10 Holdings by Portfolio Weight',
            yaxis={'title': 'Weight (%)'},
            margin={'t': 40, 'b': 80, 'l': 40, 'r': 40},
        ),
    }

    return html.Div([
        html.Hr(),
        html.H4("Portfolio Analytics"),
        kpi_row,
        kpi_row_2,
        html.Hr(),

        # Benchmark comparison
        _build_benchmark_section(),
        html.Hr(),

        # Drawdown chart
        _build_drawdown_chart(drawdown_series),
        html.Hr(),

        # Top holdings
        html.Div([
            dcc.Graph(id='top-holdings-chart', figure=weight_chart)
        ], className="card", style=Styles.STYLE(100)),
        html.Hr(),

        # P&L charts
        html.Div([
            dcc.Graph(id='pnl-by-holding-chart', figure=pnl_chart)
        ], className="card", style=Styles.STYLE(48)),
        html.Div([''], style=Styles.FILLER()),
        html.Div([
            dcc.Graph(id='return-by-holding-chart', figure=return_chart)
        ], className="card", style=Styles.STYLE(48)),
        html.Hr(),

        # Currency impact
        html.Div([
            _build_currency_impact(df),
            html.Div([''], style=Styles.FILLER()),
        ]),

        # Expense ratio tracking
        _build_expense_ratio_section(df),
        html.Hr(),

        # Correlation heatmap
        _build_correlation_heatmap(),
        html.Hr(),

        # Sector & Geography treemaps
        _build_sector_treemap(df),
        html.Div([''], style=Styles.FILLER()),
        _build_geography_treemap(df),
    ])
