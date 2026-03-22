import numpy as np
import pandas as pd
import dash_bootstrap_components as dbc
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
        hist = dlp.load_historical_data().reset_index()
        if "date" in hist.columns:
            hist = hist.set_index("date")
        hist = 10 ** hist
        daily_returns = hist.pct_change(fill_method=None).dropna()

        # Build portfolio-weighted daily returns using current position weights
        # Match holding symbols to historical columns (handle exchange suffixes)
        holding_weights = {}
        for _, row in df.iterrows():
            sym = row.get("symbol", "")
            w = row.get("weight", 0)
            if sym in daily_returns.columns:
                holding_weights[sym] = w
            else:
                matches = [c for c in daily_returns.columns if c.startswith(sym)]
                if matches:
                    holding_weights[matches[0]] = w

        if holding_weights:
            matched_cols = list(holding_weights.keys())
            weights_arr = np.array([holding_weights[c] for c in matched_cols])
            weights_arr = weights_arr / weights_arr.sum()  # re-normalize to 1
            portfolio_daily = (daily_returns[matched_cols] * weights_arr).sum(axis=1)
        else:
            portfolio_daily = daily_returns.mean(axis=1)

        portfolio_return = float(portfolio_daily.mean() * 252)
        portfolio_vol = float(portfolio_daily.std() * np.sqrt(252))
        portfolio_sharpe = ((portfolio_return - config.RISK_FREE_RATE) / portfolio_vol
                            if portfolio_vol > 0 else None)

        # --- Sortino Ratio ---
        try:
            negative_returns = portfolio_daily[portfolio_daily < 0]
            if len(negative_returns) > 1:
                downside_deviation = float(negative_returns.std() * np.sqrt(252))
                if downside_deviation > 0:
                    sortino_ratio = (portfolio_return - config.RISK_FREE_RATE) / downside_deviation
        except Exception:
            sortino_ratio = None

        # --- Max Drawdown from portfolio-weighted cumulative return ---
        try:
            cumulative = (1 + portfolio_daily).cumprod()
            running_max = cumulative.cummax()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = float(drawdown.min())
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
        # Use abs() since dividends may be stored as negative net_amount
        div_this_year = abs(dlt.total_transaction_amount(current_year, "Dividend"))
        div_last_year = abs(dlt.total_transaction_amount(current_year - 1, "Dividend"))
        # Annualize current year dividends if not full year yet
        today = datetime.today()
        day_of_year = today.timetuple().tm_yday
        days_in_year = 366 if (current_year % 4 == 0 and (current_year % 100 != 0 or current_year % 400 == 0)) else 365
        if day_of_year > 30 and div_this_year > 0:
            annualized_this_year = div_this_year * (days_in_year / day_of_year)
        else:
            annualized_this_year = div_this_year
        if div_last_year > 0:
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
        html.Div([
            dcc.Graph(id='expense-ratio-chart', figure=chart)
        ], className="card"),
    ])

def _build_fee_drag_section(df):
    """Build cumulative fee drag analysis showing the impact of ETF expense ratios over time."""
    if df.empty or "asset_type" not in df.columns:
        return html.Div()

    # ── Identify ETFs with TER data ──
    etfs = df[df["asset_type"].str.lower().isin(["etf", "etfs"])].copy()
    if etfs.empty:
        return html.Div()

    etfs["ter"] = etfs["symbol"].map(config.ETF_EXPENSE_RATIOS).fillna(0)
    etfs_with_ter = etfs[etfs["ter"] > 0].copy()
    if etfs_with_ter.empty:
        return html.Div()

    total_etf_value = etfs_with_ter["market_value"].sum()
    weighted_ter = ((etfs_with_ter["ter"] * etfs_with_ter["market_value"]).sum()
                    / total_etf_value) if total_etf_value > 0 else 0

    # ── Load historical price data ──
    try:
        hist = dlp.load_historical_data().reset_index()
        if "date" in hist.columns:
            hist = hist.set_index("date")
        hist = 10 ** hist  # convert from log scale
    except Exception:
        return html.Div()

    # Map position symbols to historical columns (handle exchange suffixes)
    symbol_to_col = {}
    for sym in etfs_with_ter["symbol"].values:
        if sym in hist.columns:
            symbol_to_col[sym] = sym
        else:
            # Try matching with exchange suffix (e.g. SPICHA → SPICHA.SW)
            matches = [c for c in hist.columns if c.startswith(sym)]
            if matches:
                symbol_to_col[sym] = matches[0]

    if not symbol_to_col:
        return html.Div()

    # ── Compute per-ETF actual vs fee-free returns ──
    weights = {}
    for sym in symbol_to_col:
        row = etfs_with_ter[etfs_with_ter["symbol"] == sym]
        if not row.empty:
            weights[sym] = row["market_value"].values[0] / total_etf_value

    # Build weighted actual and fee-free series
    actual_weighted = None
    feefree_weighted = None

    for sym, col in symbol_to_col.items():
        if sym not in weights:
            continue
        prices = hist[col].dropna()
        if len(prices) < 2:
            continue

        ter = config.ETF_EXPENSE_RATIOS.get(sym, 0)
        daily_ter = ter / 252
        w = weights[sym]

        # Normalize to 100
        first_price = prices.iloc[0]
        normalized = (prices / first_price) * 100

        # Daily returns (already net of fees — fees are baked into ETF NAV)
        daily_returns = prices.pct_change().dropna()

        # Fee-free return: add back the daily TER to each day's return
        gross_daily = daily_returns + daily_ter
        feefree = (1 + gross_daily).cumprod() * 100
        feefree = pd.concat([pd.Series([100], index=[prices.index[0]]), feefree])

        # Align to same index
        actual_series = normalized.reindex(feefree.index)

        if actual_weighted is None:
            actual_weighted = actual_series * w
            feefree_weighted = feefree * w
        else:
            # Align all series to common index
            common_idx = actual_weighted.index.intersection(actual_series.index)
            actual_weighted = actual_weighted.reindex(common_idx) + actual_series.reindex(common_idx) * w
            feefree_weighted = feefree_weighted.reindex(common_idx) + feefree.reindex(common_idx) * w

    if actual_weighted is None or feefree_weighted is None:
        return html.Div()

    actual_weighted = actual_weighted.dropna()
    feefree_weighted = feefree_weighted.reindex(actual_weighted.index).dropna()

    # ── Fee drag in currency terms ──
    # The percentage gap applied to current ETF value
    drag_pct = (feefree_weighted - actual_weighted) / 100  # as fraction of initial
    cumulative_drag_currency = drag_pct * total_etf_value

    # Current total drag
    total_drag = cumulative_drag_currency.iloc[-1] if not cumulative_drag_currency.empty else 0

    # ── 10-Year projection ──
    # Assume portfolio grows at expected return, fees compound annually
    g = config.EXPECTED_RETURN
    if g > 0:
        # Sum of geometric series: TER × value × Σ(1+g)^i for i=0..9
        geo_sum = ((1 + g) ** 10 - 1) / g
    else:
        geo_sum = 10
    projected_10yr = total_etf_value * weighted_ter * geo_sum

    # ── KPIs ──
    kpis = html.Div([
        Styles.kpiboxes("Total Fee Drag", f"{total_drag:,.0f}", Styles.strongRed),
        Styles.kpiboxes("Weighted TER", f"{weighted_ter:.2%}", Styles.colorPalette[3]),
        Styles.kpiboxes("10-Yr Projected Drag", f"{projected_10yr:,.0f}", Styles.colorPalette[2]),
    ], className="kpi-row")

    # ── Chart 1: Cumulative fee drag (area) ──
    drag_chart = {
        'data': [{
            'type': 'scatter',
            'x': cumulative_drag_currency.index.tolist(),
            'y': cumulative_drag_currency.round(0).tolist(),
            'mode': 'lines',
            'fill': 'tozeroy',
            'fillcolor': 'rgba(255, 59, 48, 0.15)',
            'line': {'color': Styles.strongRed, 'width': 2},
            'name': 'Cumulative Fees',
            'hovertemplate': '%{x}<br>Fee Drag: %{y:,.0f}<extra></extra>',
        }],
        'layout': Styles.graph_layout(
            title='Cumulative Fee Drag',
            xaxis={'title': 'Date', 'type': 'date'},
            yaxis={'title': 'Fees Paid (est.)'},
            hovermode='x unified',
        ),
    }

    # ── Chart 2: Actual vs fee-free return (lines) ──
    comparison_chart = {
        'data': [
            {
                'type': 'scatter',
                'x': actual_weighted.index.tolist(),
                'y': actual_weighted.round(2).tolist(),
                'mode': 'lines',
                'name': 'Actual (net of fees)',
                'line': {'color': Styles.colorPalette[0], 'width': 2},
            },
            {
                'type': 'scatter',
                'x': feefree_weighted.index.tolist(),
                'y': feefree_weighted.round(2).tolist(),
                'mode': 'lines',
                'name': 'Without Fees',
                'line': {'color': Styles.colorPalette[1], 'width': 2, 'dash': 'dash'},
            },
        ],
        'layout': Styles.graph_layout(
            title='ETF Returns: Actual vs Fee-Free',
            xaxis={'title': 'Date', 'type': 'date'},
            yaxis={'title': 'Indexed Value (100 = start)'},
            hovermode='x unified',
            legend={'orientation': 'h', 'y': -0.15, 'x': 0.5, 'xanchor': 'center'},
            margin={'b': 60},
        ),
    }

    return html.Div([
        html.H5("Fee Drag Analysis"),
        kpis,
        html.Div([
            html.Div([
                dcc.Graph(id='fee-drag-chart', figure=drag_chart)
            ], className="card"),
            html.Div([
                dcc.Graph(id='fee-comparison-chart', figure=comparison_chart)
            ], className="card"),
        ], className="grid-2"),
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
    ], className="card")

def _build_benchmark_section():
    """Build benchmark comparison chart with SPY/MSCI World overlays."""
    try:
        hist = dlp.load_historical_data().reset_index()
        if "date" in hist.columns:
            hist = hist.set_index("date")
        hist = 10 ** hist
    except Exception:
        return html.Div()

    if hist.empty or hist.shape[1] < 2:
        return html.Div()

    # Separate benchmark columns from portfolio holdings
    bench_tickers = config.BENCHMARK_TICKERS
    holding_cols = [c for c in hist.columns if c not in bench_tickers]
    bench_cols = [c for c in bench_tickers if c in hist.columns]

    # Normalize all to 100 at start
    first_valid = hist.apply(lambda s: s.dropna().iloc[0] if not s.dropna().empty else np.nan)
    normalized = (hist / first_valid) * 100

    # Portfolio average from HOLDINGS ONLY (exclude benchmarks)
    if holding_cols:
        portfolio_avg = normalized[holding_cols].mean(axis=1).dropna()
    else:
        portfolio_avg = normalized.mean(axis=1).dropna()

    # ── Traces ──
    traces = [{
        'x': portfolio_avg.index.tolist(),
        'y': portfolio_avg.round(2).tolist(),
        'type': 'scatter',
        'mode': 'lines',
        'name': 'Portfolio',
        'line': {'color': Styles.colorPalette[0], 'width': 3},
    }]

    # Benchmark overlays (bold dashed lines)
    bench_colors = [Styles.colorPalette[2], Styles.strongGreen]
    for i, col in enumerate(bench_cols):
        series = normalized[col].dropna()
        if not series.empty:
            label = config.BENCHMARK_NAMES.get(col, col)
            traces.append({
                'x': series.index.tolist(),
                'y': series.round(2).tolist(),
                'type': 'scatter',
                'mode': 'lines',
                'name': label,
                'line': {'color': bench_colors[i % len(bench_colors)],
                         'width': 2, 'dash': 'dash'},
            })

    # Individual holdings as faint lines
    for col in holding_cols:
        series = normalized[col].dropna()
        if not series.empty:
            traces.append({
                'x': series.index.tolist(),
                'y': series.round(2).tolist(),
                'type': 'scatter',
                'mode': 'lines',
                'name': col,
                'line': {'width': 1},
                'opacity': 0.35,
            })

    chart = {
        'data': traces,
        'layout': Styles.graph_layout(
            title='Portfolio vs Benchmarks (Normalized to 100)',
            xaxis={'title': 'Date', 'type': 'date'},
            yaxis={'title': 'Indexed Value'},
            hovermode='x unified',
            legend={'orientation': 'h', 'y': -0.12, 'x': 0.5, 'xanchor': 'center'},
            margin={'b': 60},
        ),
    }

    # ── Alpha KPIs ──
    alpha_kpis = []
    portfolio_final = portfolio_avg.iloc[-1] if not portfolio_avg.empty else 100
    portfolio_return = portfolio_final - 100

    for col in bench_cols:
        series = normalized[col].dropna()
        if not series.empty:
            bench_final = series.iloc[-1]
            bench_return = bench_final - 100
            alpha = portfolio_return - bench_return
            label = config.BENCHMARK_NAMES.get(col, col)
            color = Styles.strongGreen if alpha >= 0 else Styles.strongRed
            alpha_kpis.append(
                Styles.kpiboxes(f"Alpha vs {label}", f"{alpha:+.1f}%", color)
            )

    alpha_kpis.insert(0, Styles.kpiboxes(
        "Portfolio Return", f"{portfolio_return:+.1f}%",
        Styles.strongGreen if portfolio_return >= 0 else Styles.strongRed))

    return html.Div([
        html.Div(alpha_kpis, className="kpi-row"),
        dcc.Graph(id='benchmark-chart', figure=chart),
    ], className="card")

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
    ], className="card")

def _build_correlation_heatmap():
    """Build a correlation matrix heatmap from historical returns."""
    try:
        hist = dlp.load_historical_data().reset_index()
        if "date" in hist.columns:
            hist = hist.set_index("date")
        hist = 10 ** hist
        daily_returns = hist.pct_change(fill_method=None).dropna()
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
    ], className="card")

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
    ], className="card")

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
    ], className="card")

def layout():
    df, metrics, drawdown_series = _compute_analytics()

    if df.empty:
        return html.Div([
            html.H4("No portfolio data available."),
        ])

    # --- KPI row 1 (existing) ---
    kpi_row = html.Div([
        Styles.kpiboxes('Portfolio Sharpe', metrics.get("sharpe", "N/A"), Styles.colorPalette[0]),
        Styles.kpiboxes('Est. Annual Return', metrics.get("annual_return", "N/A"), Styles.colorPalette[1]),
        Styles.kpiboxes('Est. Annual Vol', metrics.get("annual_vol", "N/A"), Styles.colorPalette[2]),
        Styles.kpiboxes('Total Market Value', f"{metrics.get('total_mv', 0):,}", Styles.colorPalette[3]),
        Styles.kpiboxes('Risk-Free Rate', f"{config.RISK_FREE_RATE:.1%}", Styles.colorPalette[1]),
    ], className="kpi-row")

    # --- KPI row 2 (advanced metrics) ---
    kpi_row_2 = html.Div([
        Styles.kpiboxes('CAGR', metrics.get("cagr", "N/A"), Styles.colorPalette[0]),
        Styles.kpiboxes('Max Drawdown', metrics.get("max_drawdown", "N/A"), Styles.colorPalette[1]),
        Styles.kpiboxes('Sortino Ratio', metrics.get("sortino", "N/A"), Styles.colorPalette[2]),
        Styles.kpiboxes('Concentration', metrics.get("concentration", "N/A"), Styles.colorPalette[3]),
        Styles.kpiboxes('Dividend Growth', metrics.get("div_growth", "N/A"), Styles.colorPalette[0]),
    ], className="kpi-row")

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
        html.H4("Portfolio Analytics"),
        dcc.Loading(type="circle", children=[
            kpi_row,
            kpi_row_2,

            # ── Tabbed sections ──
            html.Div([
                dbc.Tabs([
                    dbc.Tab([
                        _build_benchmark_section(),
                        _build_drawdown_chart(drawdown_series),
                    ], label="Performance", tab_id="tab-performance"),

                    dbc.Tab([
                        html.Div([
                            dcc.Graph(id='top-holdings-chart', figure=weight_chart)
                        ], className="card"),
                        html.Div([
                            html.Div([
                                dcc.Graph(id='pnl-by-holding-chart', figure=pnl_chart)
                            ], className="card"),
                            html.Div([
                                dcc.Graph(id='return-by-holding-chart', figure=return_chart)
                            ], className="card"),
                        ], className="grid-2"),
                    ], label="Holdings", tab_id="tab-holdings"),

                    dbc.Tab([
                        _build_currency_impact(df),
                        _build_expense_ratio_section(df),
                        _build_fee_drag_section(df),
                    ], label="Costs", tab_id="tab-costs"),

                    dbc.Tab([
                        _build_correlation_heatmap(),
                        html.Div([
                            _build_sector_treemap(df),
                            _build_geography_treemap(df),
                        ], className="grid-2"),
                    ], label="Risk & Diversification", tab_id="tab-risk"),
                ], active_tab="tab-performance"),
            ], className="analytics-tabs"),
        ]),
    ])
