# pages/page_backtest.py — Strategy Backtester dashboard page
#
# Signal-driven long-only strategy across ETFs, bonds, and commodities.
# Monthly rebalancing based on macro signal scores.

from dash import dcc, html, Input, Output, State
import dash
import plotly.graph_objects as go
import numpy as np

import Styles
import config
import backtestEngine as bte


# ─────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────

def layout():
    return html.Div([
        html.H4("Strategy Backtester"),
        html.P(
            "Signal-driven long-only strategy across ETFs, bonds, and commodities. "
            "Monthly rebalancing based on macro signal scores. Adjust sensitivity to "
            "control how aggressively signals tilt allocations from the base weights.",
            style={"fontSize": "13px", "color": "var(--text-muted, #888)",
                   "margin": "0 0 16px 0", "maxWidth": "720px"},
        ),

        # --- Controls row ---
        html.Div([
            html.Div([
                html.Label("Signal Sensitivity", style={"fontWeight": "600",
                            "fontSize": "0.8125rem"}),
                dcc.Slider(
                    id="bt-sensitivity", min=0, max=3, step=0.1, value=1.0,
                    marks={i: str(i) for i in [0, 0.5, 1, 1.5, 2, 2.5, 3]},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ], style={"width": "36%", "display": "inline-block",
                      "padding": "10px 20px", "verticalAlign": "top"}),

            html.Div([
                html.Label("Optimize For", style={"fontWeight": "600",
                            "fontSize": "0.8125rem"}),
                dcc.Dropdown(
                    id="bt-target",
                    options=[
                        {"label": "Alpha vs S&P 500", "value": "alpha_spy"},
                        {"label": "Alpha vs MSCI World", "value": "alpha_urth"},
                        {"label": "Sharpe Ratio", "value": "sharpe"},
                    ],
                    value="alpha_spy", clearable=False,
                    style={"marginTop": "4px"},
                ),
            ], style={"width": "22%", "display": "inline-block",
                      "padding": "10px 20px", "verticalAlign": "top"}),

            html.Div([
                html.Button("Run Backtest", id="bt-run-btn",
                            className="header-btn",
                            style={"marginTop": "22px"}),
                html.Button("Find Optimal", id="bt-optimize-btn",
                            className="header-btn-outline",
                            style={"marginLeft": "8px", "marginTop": "22px"}),
            ], style={"width": "36%", "display": "inline-block",
                      "padding": "10px 20px", "verticalAlign": "top"}),
        ], style={"marginBottom": "20px"}),

        # --- Results area ---
        dcc.Loading(
            html.Div(id="bt-results", children=html.Div([
                Styles.skeleton_kpis(5),
                Styles.skeleton_chart(),
            ])),
            type="dot",
        ),
    ])


# ─────────────────────────────────────────────
# Chart builders
# ─────────────────────────────────────────────

def _equity_curve_chart(result_df):
    """Equity curve: Strategy vs SPY vs URTH, normalised to 100."""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=result_df.index, y=result_df["portfolio"],
        name="Strategy", mode="lines",
        line=dict(color=Styles.colorPalette[1], width=2.5),
    ))
    fig.add_trace(go.Scatter(
        x=result_df.index, y=result_df["spy"],
        name="S&P 500", mode="lines",
        line=dict(color=Styles.strongGreen, width=1.5, dash="dash"),
    ))
    fig.add_trace(go.Scatter(
        x=result_df.index, y=result_df["urth"],
        name="MSCI World", mode="lines",
        line=dict(color=Styles.colorPalette[3], width=1.5, dash="dash"),
    ))

    fig.update_layout(**Styles.graph_layout(
        title="Equity Curve (normalised to 100)",
        legend=dict(orientation="h", y=1.02, x=0),
        yaxis=dict(title="Value"),
        hovermode="x unified",
    ))
    return fig


def _drawdown_chart(result_df):
    """Portfolio drawdown from peak."""
    cummax = result_df["portfolio"].cummax()
    dd = (result_df["portfolio"] - cummax) / cummax * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dd.index, y=dd.values,
        fill="tozeroy", mode="lines",
        line=dict(color=Styles.strongRed, width=1),
        fillcolor="rgba(255, 59, 48, 0.25)",
        name="Drawdown",
    ))
    fig.update_layout(**Styles.graph_layout(
        title="Drawdown from Peak",
        yaxis=dict(title="Drawdown %", ticksuffix="%"),
        hovermode="x unified",
    ))
    return fig


def _signal_chart(result_df):
    """Signal score at each rebalance date."""
    signals = result_df["signal_score"].dropna()
    if signals.empty:
        return go.Figure()

    colors = [Styles.strongGreen if v >= 0 else Styles.strongRed for v in signals.values]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=signals.index, y=signals.values,
        marker_color=colors, name="Signal Score",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color="grey", opacity=0.5)
    fig.add_hline(y=40, line_dash="dot", line_color=Styles.strongGreen, opacity=0.3,
                  annotation_text="BUY", annotation_position="top left")
    fig.add_hline(y=-40, line_dash="dot", line_color=Styles.strongRed, opacity=0.3,
                  annotation_text="SELL", annotation_position="bottom left")
    fig.update_layout(**Styles.graph_layout(
        title="Signal Score at Rebalance",
        yaxis=dict(title="Score", range=[-110, 110]),
        hovermode="x unified",
    ))
    return fig


def _allocation_chart(result_df):
    """Stacked area of asset weights over time."""
    assets = config.BACKTEST_ASSETS
    weight_cols = [f"w_{k}" for k in assets]
    available = [c for c in weight_cols if c in result_df.columns]

    if not available:
        return go.Figure()

    # Forward-fill weight columns (only change at rebalance)
    w_df = result_df[available].ffill()

    # Use a nice color palette
    palette = Styles.purple_list + [Styles.strongGreen, Styles.strongRed,
                                     "#f5a623", "#8e44ad"]
    fig = go.Figure()
    for i, col in enumerate(available):
        asset_key = col.replace("w_", "")
        label = assets.get(asset_key, {}).get("name", asset_key)
        fig.add_trace(go.Scatter(
            x=w_df.index, y=w_df[col] * 100,
            name=label, stackgroup="one", mode="lines",
            line=dict(width=0.5, color=palette[i % len(palette)]),
        ))

    fig.update_layout(**Styles.graph_layout(
        title="Asset Allocation Over Time",
        yaxis=dict(title="Weight %", range=[0, 105], ticksuffix="%"),
        legend=dict(orientation="h", y=-0.15, x=0),
        hovermode="x unified",
    ))
    return fig


def _sensitivity_chart(all_results, target, optimal_s):
    """Sensitivity sweep: target metric vs sensitivity parameter."""
    if not all_results:
        return go.Figure()

    sensitivities = [r[0] for r in all_results]
    values = [r[1].get(target, 0) for r in all_results]

    # Format values based on target
    is_pct = target in ("alpha_spy", "alpha_urth", "cagr")
    display_values = [v * 100 for v in values] if is_pct else values
    suffix = "%" if is_pct else ""

    target_labels = {
        "alpha_spy": "Alpha vs S&P 500",
        "alpha_urth": "Alpha vs MSCI World",
        "sharpe": "Sharpe Ratio",
    }

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=sensitivities, y=display_values,
        mode="lines+markers",
        line=dict(color=Styles.colorPalette[1], width=2),
        marker=dict(size=5),
        name=target_labels.get(target, target),
    ))

    # Mark optimal point
    if optimal_s is not None:
        opt_idx = next((i for i, s in enumerate(sensitivities) if s == optimal_s), None)
        if opt_idx is not None:
            fig.add_trace(go.Scatter(
                x=[optimal_s], y=[display_values[opt_idx]],
                mode="markers",
                marker=dict(size=14, color=Styles.strongGreen, symbol="star"),
                name=f"Optimal ({optimal_s})",
                showlegend=True,
            ))

    fig.add_vline(x=optimal_s, line_dash="dash",
                  line_color=Styles.strongGreen, opacity=0.5)

    fig.update_layout(**Styles.graph_layout(
        title=f"Sensitivity Sweep — {target_labels.get(target, target)}",
        xaxis=dict(title="Sensitivity"),
        yaxis=dict(title=target_labels.get(target, target),
                   ticksuffix=suffix),
        hovermode="x unified",
    ))
    return fig


# ─────────────────────────────────────────────
# KPI builder
# ─────────────────────────────────────────────

def _build_kpis(metrics):
    """Build KPI row from metrics dict."""
    def _color(val):
        return Styles.strongGreen if val >= 0 else Styles.strongRed

    return html.Div([
        Styles.kpiboxes("CAGR",
                        f"{metrics['cagr'] * 100:+.1f}%",
                        _color(metrics["cagr"])),
        Styles.kpiboxes("Sharpe Ratio",
                        f"{metrics['sharpe']:.2f}",
                        Styles.colorPalette[0]),
        Styles.kpiboxes("Max Drawdown",
                        f"{metrics['max_drawdown'] * 100:.1f}%",
                        Styles.strongRed),
        Styles.kpiboxes("Alpha vs SPY",
                        f"{metrics['alpha_spy'] * 100:+.1f}%",
                        _color(metrics["alpha_spy"])),
        Styles.kpiboxes("Alpha vs URTH",
                        f"{metrics['alpha_urth'] * 100:+.1f}%",
                        _color(metrics["alpha_urth"])),
        Styles.kpiboxes("Sortino Ratio",
                        f"{metrics['sortino']:.2f}",
                        Styles.colorPalette[0]),
        Styles.kpiboxes("Annual Volatility",
                        f"{metrics['annual_vol'] * 100:.1f}%",
                        Styles.colorPalette[1]),
    ], className="kpi-row")


def _build_benchmark_kpis(metrics):
    """Show benchmark returns for context."""
    return html.Div([
        Styles.kpiboxes("SPY CAGR",
                        f"{metrics['spy_cagr'] * 100:+.1f}%",
                        Styles.colorPalette[2]),
        Styles.kpiboxes("URTH CAGR",
                        f"{metrics['urth_cagr'] * 100:+.1f}%",
                        Styles.colorPalette[2]),
        Styles.kpiboxes("Total Return",
                        f"{metrics['total_return'] * 100:+.1f}%",
                        Styles.colorPalette[0]),
    ], className="kpi-row")


# ─────────────────────────────────────────────
# Full results renderer
# ─────────────────────────────────────────────

def _render_backtest_results(result_df, metrics, opt_results=None,
                              opt_target=None, opt_sensitivity=None):
    """Build the full results section."""
    children = []

    # KPIs
    children.append(_build_kpis(metrics))
    children.append(_build_benchmark_kpis(metrics))

    # Equity curve (full width)
    children.append(html.Div(
        dcc.Graph(figure=_equity_curve_chart(result_df),
                  config={"displayModeBar": False}),
        className="card", style={"marginTop": "16px"},
    ))

    # Drawdown + Signal score (grid-2)
    children.append(html.Div([
        html.Div(
            dcc.Graph(figure=_drawdown_chart(result_df),
                      config={"displayModeBar": False}),
            className="card",
        ),
        html.Div(
            dcc.Graph(figure=_signal_chart(result_df),
                      config={"displayModeBar": False}),
            className="card",
        ),
    ], className="grid-2", style={"marginTop": "12px"}))

    # Allocation over time (full width)
    children.append(html.Div(
        dcc.Graph(figure=_allocation_chart(result_df),
                  config={"displayModeBar": False}),
        className="card", style={"marginTop": "12px"},
    ))

    # Sensitivity sweep (only shown after optimization)
    if opt_results:
        children.append(html.Div(
            dcc.Graph(figure=_sensitivity_chart(
                opt_results, opt_target, opt_sensitivity),
                config={"displayModeBar": False}),
            className="card", style={"marginTop": "12px"},
        ))

    # Disclaimer
    children.append(html.P(
        "Past performance does not guarantee future results. "
        "This backtest uses historical data and does not account for "
        "transaction costs, slippage, or taxes.",
        style={"fontSize": "0.75rem", "color": "var(--text-muted, #888)",
               "marginTop": "16px", "fontStyle": "italic"},
    ))

    return html.Div(children)


# ─────────────────────────────────────────────
# Callbacks
# ─────────────────────────────────────────────

def register_callbacks(app):

    @app.callback(
        [Output("bt-results", "children"),
         Output("bt-sensitivity", "value")],
        [Input("bt-run-btn", "n_clicks"),
         Input("bt-optimize-btn", "n_clicks")],
        [State("bt-sensitivity", "value"),
         State("bt-target", "value")],
        prevent_initial_call=True,
    )
    def update_backtest(run_clicks, opt_clicks, sensitivity, target):
        import logging
        logger = logging.getLogger(__name__)
        try:
            ctx = dash.callback_context
            if not ctx.triggered:
                return dash.no_update, dash.no_update
            trigger = ctx.triggered[0]["prop_id"]

            df = bte.load_and_prepare()
            if df.empty:
                return html.P("No macro data available. Please refresh data first.",
                              style={"color": Styles.strongRed}), sensitivity

            if "bt-optimize-btn" in trigger:
                opt = bte.optimize_alpha(df, target=target)
                if not opt["all_results"]:
                    return html.P("Optimization produced no results.",
                                  style={"color": Styles.strongRed}), sensitivity

                result_df = opt["optimal_backtest"]
                metrics = opt["optimal_metrics"]
                opt_s = opt["optimal_sensitivity"]

                return _render_backtest_results(
                    result_df, metrics,
                    opt_results=opt["all_results"],
                    opt_target=target,
                    opt_sensitivity=opt_s,
                ), opt_s

            else:
                result_df = bte.run_backtest(df, sensitivity=sensitivity)
                if result_df.empty:
                    return html.P("Insufficient data for backtest.",
                                  style={"color": Styles.strongRed}), sensitivity

                metrics = bte.compute_metrics(result_df)
                return _render_backtest_results(result_df, metrics), sensitivity

        except Exception as e:
            logger.exception("Backtest callback failed")
            return html.Div([
                html.P(f"Backtest error: {e}", style={"color": Styles.strongRed}),
            ]), sensitivity or 1.0
