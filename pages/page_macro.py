# pages/page_macro.py — Macroeconomic Dashboard
from dash import dcc, html, Input, Output
import Styles
import config
import dataLoadMacro as dlm
import macroSignal


# ─────────────────────────────────────────────
# KPI builders (one per section)
# ─────────────────────────────────────────────

def _kpi(key, label=None, fmt=",.2f", invert=False):
    """Build a single KPI box with 52-week reference for a macro indicator.

    invert: if True, a rising value is colored red (e.g. VIX).
    """
    label = label or config.MACRO_NAMES.get(key, key)
    ref = dlm.get_reference_values(key)
    current = ref["current"]

    # Choose color
    if key in config.MACRO_THRESHOLDS:
        color = dlm.threshold_color(key, current)
    else:
        change = ref["yoy_change_pct"]
        if invert:
            color = Styles.strongRed if change > 0 else Styles.strongGreen
        else:
            color = Styles.strongGreen if change >= 0 else Styles.strongRed

    value_str = f"{current:{fmt}}" if current != 0 else "N/A"
    ref_label = f"52w avg: {ref['avg_52w']:{fmt}}"
    ref_pct = ref["yoy_change_pct"]
    if invert:
        ref_pct = -ref_pct  # flip arrow direction for clarity

    return Styles.kpiboxes_ref(label, value_str, color, ref_label, ref["yoy_change_pct"])


def _kpi_ratio(key_a, key_b, label, fmt=".2f"):
    """KPI for a derived ratio (e.g., Gold/Silver)."""
    ratio_series = dlm.get_ratio(key_a, key_b, period="1Y")
    if ratio_series.empty:
        return Styles.kpiboxes(label, "N/A", Styles.colorPalette[0])

    current = ratio_series.iloc[-1]
    avg = ratio_series.mean()
    pct = ((current - avg) / avg * 100) if avg != 0 else 0

    return Styles.kpiboxes_ref(
        label, f"{current:{fmt}}", Styles.colorPalette[0],
        f"1Y avg: {avg:{fmt}}", round(pct, 1),
    )


def _kpi_spread(label="10Y-2Y Spread"):
    """KPI for yield curve spread."""
    spread = dlm.get_yield_curve_spread(period="1Y")
    if spread.empty:
        return Styles.kpiboxes(label, "N/A", Styles.colorPalette[0])

    current = spread.iloc[-1]
    avg = spread.mean()
    pct = ((current - avg) / avg * 100) if avg != 0 else 0
    color = Styles.strongGreen if current >= 0 else Styles.strongRed

    return Styles.kpiboxes_ref(
        label, f"{current:.2f}%", color,
        f"1Y avg: {avg:.2f}%", round(pct, 1),
    )


# ─────────────────────────────────────────────
# Chart builders
# ─────────────────────────────────────────────

def _line_chart(keys, title, period="1Y", yaxis_title="", normalize=False):
    """Build an overlay line chart for one or more indicators."""
    traces = []
    colors = [Styles.colorPalette[0], Styles.strongGreen, Styles.colorPalette[2],
              Styles.colorPalette[3], Styles.strongRed]

    for i, key in enumerate(keys):
        series = dlm.get_indicator(key, period)
        if series.empty:
            continue

        y_vals = series.values
        if normalize and len(y_vals) > 0 and y_vals[0] != 0:
            y_vals = (y_vals / y_vals[0]) * 100

        label = config.MACRO_NAMES.get(key, key)
        traces.append({
            'x': series.index.strftime("%Y-%m-%d").tolist(),
            'y': [round(float(v), 2) for v in y_vals],
            'type': 'scatter',
            'mode': 'lines',
            'name': label,
            'line': {'color': colors[i % len(colors)], 'width': 2},
        })

    return {
        'data': traces,
        'layout': Styles.graph_layout(
            title=title,
            xaxis={'type': 'date'},
            yaxis={'title': yaxis_title},
            hovermode='x unified',
            legend={'orientation': 'h', 'y': -0.15, 'x': 0.5, 'xanchor': 'center'},
            margin={'b': 55},
        ),
    }


def _ratio_chart(key_a, key_b, title, period="1Y", yaxis_title="Ratio"):
    """Build a line chart for a derived ratio."""
    ratio = dlm.get_ratio(key_a, key_b, period)
    if ratio.empty:
        return {'data': [], 'layout': Styles.graph_layout(title=title)}

    avg = float(ratio.mean())

    return {
        'data': [
            {
                'x': ratio.index.strftime("%Y-%m-%d").tolist(),
                'y': [round(float(v), 4) for v in ratio.values],
                'type': 'scatter',
                'mode': 'lines',
                'name': title,
                'line': {'color': Styles.colorPalette[0], 'width': 2},
            },
            {
                'x': [ratio.index[0].strftime("%Y-%m-%d"),
                      ratio.index[-1].strftime("%Y-%m-%d")],
                'y': [avg, avg],
                'type': 'scatter',
                'mode': 'lines',
                'name': 'Average',
                'line': {'color': Styles.colorPalette[2], 'width': 1, 'dash': 'dash'},
            },
        ],
        'layout': Styles.graph_layout(
            title=title,
            xaxis={'type': 'date'},
            yaxis={'title': yaxis_title},
            hovermode='x unified',
            legend={'orientation': 'h', 'y': -0.15, 'x': 0.5, 'xanchor': 'center'},
            margin={'b': 55},
        ),
    }


def _spread_chart(title="Yield Curve Spread (10Y-2Y)", period="1Y"):
    """Yield curve spread with zero line."""
    spread = dlm.get_yield_curve_spread(period)
    if spread.empty:
        return {'data': [], 'layout': Styles.graph_layout(title=title)}

    colors = [Styles.strongGreen if v >= 0 else Styles.strongRed
              for v in spread.values]

    return {
        'data': [{
            'x': spread.index.strftime("%Y-%m-%d").tolist(),
            'y': [round(float(v), 3) for v in spread.values],
            'type': 'bar',
            'marker': {'color': colors},
            'name': '10Y-2Y Spread',
        }],
        'layout': Styles.graph_layout(
            title=title,
            xaxis={'type': 'date'},
            yaxis={'title': 'Spread (%)', 'zeroline': True,
                   'zerolinecolor': 'rgba(255,255,255,0.3)', 'zerolinewidth': 2},
            margin={'b': 40},
        ),
    }


def _drawdown_chart(key, title, period="1Y"):
    """ATH drawdown chart for an indicator."""
    dd = dlm.get_drawdown_from_ath(key, period)
    if dd.empty:
        return {'data': [], 'layout': Styles.graph_layout(title=title)}

    return {
        'data': [{
            'x': dd.index.strftime("%Y-%m-%d").tolist(),
            'y': [round(float(v), 2) for v in dd.values],
            'type': 'scatter',
            'mode': 'lines',
            'fill': 'tozeroy',
            'fillcolor': 'rgba(255, 59, 48, 0.15)',
            'line': {'color': Styles.strongRed, 'width': 1.5},
            'name': 'Drawdown',
            'hovertemplate': '%{x}<br>Drawdown: %{y:.1f}%<extra></extra>',
        }],
        'layout': Styles.graph_layout(
            title=title,
            xaxis={'type': 'date'},
            yaxis={'title': 'Drawdown (%)', 'ticksuffix': '%'},
            hovermode='x unified',
            margin={'b': 40},
        ),
    }


# ─────────────────────────────────────────────
# Section assemblers (called by callback)
# ─────────────────────────────────────────────

def _section_sentiment(period):
    """Market Sentiment & Volatility section."""
    kpis = html.Div([
        _kpi("vix", invert=True),
        _kpi("put_call", "Put/Call Ratio", fmt=".2f", invert=True),
        _kpi_ratio("hyg", "tlt", "HYG/TLT Ratio"),
    ], className="kpi-row")

    charts = html.Div([
        html.Div([
            dcc.Graph(figure=_line_chart(["vix"], "VIX Index", period), config={'displayModeBar': False}),
        ], className="card"),
        html.Div([
            dcc.Graph(figure=_ratio_chart("hyg", "tlt", "HYG/TLT — Credit Risk Appetite", period),
                      config={'displayModeBar': False}),
        ], className="card"),
    ], className="grid-2")

    return html.Div([
        html.Div("Market Sentiment", className="macro-section-title"),
        html.P("VIX below 15 signals complacency, above 25 elevated fear, above 35 extreme panic. "
               "A rising HYG/TLT ratio indicates risk appetite; falling signals flight to safety.",
               className="macro-section-desc"),
        kpis, charts,
    ])


def _section_rates(period):
    """Rates & Yields section."""
    kpis = html.Div([
        _kpi("us10y", "US 10Y Yield", fmt=".2f"),
        _kpi("us2y", "US 2Y Yield", fmt=".2f"),
        _kpi_spread(),
        _kpi("dxy", "Dollar Index", fmt=".1f"),
    ], className="kpi-row")

    charts = html.Div([
        html.Div([
            dcc.Graph(figure=_line_chart(["us2y", "us10y", "us30y"],
                                         "Treasury Yields", period, yaxis_title="Yield (%)"),
                      config={'displayModeBar': False}),
        ], className="card"),
        html.Div([
            dcc.Graph(figure=_spread_chart(period=period), config={'displayModeBar': False}),
        ], className="card"),
    ], className="grid-2")

    return html.Div([
        html.Div("Rates & Yields", className="macro-section-title"),
        html.P("Treasury yields reflect inflation expectations and monetary policy. "
               "A negative 10Y\u20132Y spread (inverted yield curve) has historically preceded recessions. "
               "DXY above 100 signals a strong dollar, pressuring international equities and commodities.",
               className="macro-section-desc"),
        kpis, charts,
    ])


def _section_equities(period):
    """Equity Markets section."""
    kpis = html.Div([
        _kpi("sp500", fmt=",.0f"),
        _kpi("msci_world", fmt=",.2f"),
        _kpi("em", "Emerging Markets", fmt=",.2f"),
        _kpi_ratio("em", "spy", "EM/US Ratio"),
    ], className="kpi-row")

    charts = html.Div([
        html.Div([
            dcc.Graph(figure=_line_chart(["sp500", "msci_world", "em"],
                                         "Global Equity Indices (Normalized)", period,
                                         yaxis_title="Indexed (100)", normalize=True),
                      config={'displayModeBar': False}),
        ], className="card"),
        html.Div([
            dcc.Graph(figure=_ratio_chart("em", "spy", "EM vs US Relative Strength", period),
                      config={'displayModeBar': False}),
        ], className="card"),
    ], className="grid-2")

    return html.Div([
        html.Div("Equity Markets", className="macro-section-title"),
        html.P("Global equity indices normalized to 100 at period start for relative comparison. "
               "A rising EM/US ratio signals emerging-market outperformance versus U.S. equities.",
               className="macro-section-desc"),
        kpis, charts,
    ])


def _section_commodities(period):
    """Commodities section."""
    kpis = html.Div([
        _kpi("gold", fmt=",.0f"),
        _kpi("silver", fmt=",.2f"),
        _kpi_ratio("gold", "silver", "Gold/Silver Ratio", fmt=".1f"),
        _kpi("oil", "Crude Oil (WTI)", fmt=",.2f"),
    ], className="kpi-row")

    charts = html.Div([
        html.Div([
            dcc.Graph(figure=_line_chart(["gold", "silver", "oil"],
                                         "Commodities (Normalized)", period,
                                         yaxis_title="Indexed (100)", normalize=True),
                      config={'displayModeBar': False}),
        ], className="card"),
        html.Div([
            dcc.Graph(figure=_ratio_chart("gold", "silver", "Gold/Silver Ratio", period),
                      config={'displayModeBar': False}),
        ], className="card"),
    ], className="grid-2")

    return html.Div([
        html.Div("Commodities", className="macro-section-title"),
        html.P("Gold/Silver ratio above 80 historically signals risk aversion; below 60 suggests growth optimism. "
               "Rising oil prices add inflationary pressure and weigh on consumer spending.",
               className="macro-section-desc"),
        kpis, charts,
    ])


def _section_crypto(period):
    """Crypto section."""
    # BTC drawdown KPI
    dd_btc = dlm.get_drawdown_from_ath("btc", period="5Y")
    btc_dd_val = f"{dd_btc.iloc[-1]:.1f}%" if not dd_btc.empty else "N/A"
    dd_color = Styles.strongRed if not dd_btc.empty and dd_btc.iloc[-1] < -20 else Styles.strongGreen

    kpis = html.Div([
        _kpi("btc", "Bitcoin", fmt=",.0f"),
        _kpi("eth", "Ethereum", fmt=",.2f"),
        Styles.kpiboxes("BTC Drawdown", btc_dd_val, dd_color),
    ], className="kpi-row")

    charts = html.Div([
        html.Div([
            dcc.Graph(figure=_line_chart(["btc", "eth"], "Crypto Prices", period),
                      config={'displayModeBar': False}),
        ], className="card"),
        html.Div([
            dcc.Graph(figure=_drawdown_chart("btc", "Bitcoin — Drawdown from ATH", period),
                      config={'displayModeBar': False}),
        ], className="card"),
    ], className="grid-2")

    return html.Div([
        html.Div("Crypto", className="macro-section-title"),
        html.P("Bitcoin drawdown from all-time high gauges cycle positioning. "
               "Drawdowns beyond \u221220% are common in corrections; beyond \u221250% typically mark bear markets.",
               className="macro-section-desc"),
        kpis, charts,
    ])


# ─────────────────────────────────────────────
# Predictive section — charts & KPIs
# ─────────────────────────────────────────────

def _ma_overlay_chart(key, period="1Y"):
    """Price line with 50- and 200-day moving-average overlay."""
    price = dlm.get_indicator(key, period)
    ma50 = dlm.get_moving_average(key, 50, period)
    ma200 = dlm.get_moving_average(key, 200, period)

    label = config.MACRO_NAMES.get(key, key)
    traces = []

    if not price.empty:
        traces.append({
            'x': price.index.strftime("%Y-%m-%d").tolist(),
            'y': [round(float(v), 2) for v in price.values],
            'type': 'scatter', 'mode': 'lines',
            'name': label,
            'line': {'color': Styles.colorPalette[0], 'width': 2},
        })
    if not ma50.empty:
        traces.append({
            'x': ma50.index.strftime("%Y-%m-%d").tolist(),
            'y': [round(float(v), 2) for v in ma50.values],
            'type': 'scatter', 'mode': 'lines',
            'name': '50 DMA',
            'line': {'color': Styles.strongGreen, 'width': 1.5, 'dash': 'dot'},
        })
    if not ma200.empty:
        traces.append({
            'x': ma200.index.strftime("%Y-%m-%d").tolist(),
            'y': [round(float(v), 2) for v in ma200.values],
            'type': 'scatter', 'mode': 'lines',
            'name': '200 DMA',
            'line': {'color': Styles.strongRed, 'width': 1.5, 'dash': 'dash'},
        })

    return {
        'data': traces,
        'layout': Styles.graph_layout(
            title=f"{label} — 50/200 Day Moving Averages",
            xaxis={'type': 'date'},
            yaxis={'title': 'Price'},
            hovermode='x unified',
            legend={'orientation': 'h', 'y': -0.15, 'x': 0.5, 'xanchor': 'center'},
            margin={'b': 55},
        ),
    }


def _vix_term_chart(period="1Y"):
    """VIX vs VIX3M overlay chart."""
    vix = dlm.get_indicator("vix", period)
    vix3m = dlm.get_indicator("vix3m", period)

    traces = []
    if not vix.empty:
        traces.append({
            'x': vix.index.strftime("%Y-%m-%d").tolist(),
            'y': [round(float(v), 2) for v in vix.values],
            'type': 'scatter', 'mode': 'lines',
            'name': 'VIX (Near-Term)',
            'line': {'color': Styles.strongRed, 'width': 2},
        })
    if not vix3m.empty:
        traces.append({
            'x': vix3m.index.strftime("%Y-%m-%d").tolist(),
            'y': [round(float(v), 2) for v in vix3m.values],
            'type': 'scatter', 'mode': 'lines',
            'name': 'VIX3M (3-Month)',
            'line': {'color': Styles.colorPalette[0], 'width': 2, 'dash': 'dash'},
        })

    return {
        'data': traces,
        'layout': Styles.graph_layout(
            title="VIX Term Structure — Near vs 3-Month",
            xaxis={'type': 'date'},
            yaxis={'title': 'VIX Level'},
            hovermode='x unified',
            legend={'orientation': 'h', 'y': -0.15, 'x': 0.5, 'xanchor': 'center'},
            margin={'b': 55},
        ),
    }


def _roc_chart(key="sp500", periods=20, period="1Y"):
    """Rate of Change (momentum) chart with zero reference line."""
    roc = dlm.get_rate_of_change(key, periods, period)
    label = config.MACRO_NAMES.get(key, key)

    if roc.empty:
        return {'data': [], 'layout': Styles.graph_layout(
            title=f"{label} — {periods}-Day Rate of Change")}

    colors = [Styles.strongGreen if v >= 0 else Styles.strongRed
              for v in roc.values]

    return {
        'data': [{
            'x': roc.index.strftime("%Y-%m-%d").tolist(),
            'y': [round(float(v), 2) for v in roc.values],
            'type': 'bar',
            'marker': {'color': colors},
            'name': f'{periods}d ROC',
        }],
        'layout': Styles.graph_layout(
            title=f"{label} — {periods}-Day Rate of Change",
            xaxis={'type': 'date'},
            yaxis={'title': 'ROC (%)', 'zeroline': True,
                   'zerolinecolor': 'rgba(255,255,255,0.3)', 'zerolinewidth': 2},
            margin={'b': 40},
        ),
    }


def _slope_trend_chart(period="1Y"):
    """Yield curve slope momentum (20-day change in spread) as bar chart."""
    momentum = dlm.get_yield_slope_momentum(period)

    if momentum.empty:
        return {'data': [], 'layout': Styles.graph_layout(
            title="Yield Curve Slope Momentum")}

    colors = [Styles.strongGreen if v >= 0 else Styles.strongRed
              for v in momentum.values]

    return {
        'data': [{
            'x': momentum.index.strftime("%Y-%m-%d").tolist(),
            'y': [round(float(v), 4) for v in momentum.values],
            'type': 'bar',
            'marker': {'color': colors},
            'name': 'Slope Change (20d)',
        }],
        'layout': Styles.graph_layout(
            title="Yield Curve Slope Momentum (20-Day Change)",
            xaxis={'type': 'date'},
            yaxis={'title': 'Spread Change (pp)', 'zeroline': True,
                   'zerolinecolor': 'rgba(255,255,255,0.3)', 'zerolinewidth': 2},
            margin={'b': 40},
        ),
    }


def _kpi_ma_status(key, label):
    """KPI box showing moving-average alignment status."""
    status = dlm.get_ma_crossover_status(key, short=50, long=200)
    if status["price"] == 0:
        return Styles.kpiboxes(f"{label} DMA", "N/A", Styles.colorPalette[0])

    if status["cross_signal"] == "golden_cross":
        text, color = "Golden Cross", Styles.strongGreen
    elif status["cross_signal"] == "death_cross":
        text, color = "Death Cross", Styles.strongRed
    elif status["price_above_short"] and status["price_above_long"] and status["aligned"]:
        text, color = "Bullish", Styles.strongGreen
    elif not status["price_above_short"] and not status["price_above_long"] and not status["aligned"]:
        text, color = "Bearish", Styles.strongRed
    elif status["price_above_long"]:
        text, color = "Above 200d", Styles.colorPalette[1]
    else:
        text, color = "Mixed", Styles.colorPalette[3]

    ref_label = f"50d: {status['ma_short']:,.0f}  200d: {status['ma_long']:,.0f}"
    return Styles.kpiboxes_ref(f"{label} DMA", text, color, ref_label, None)


def _kpi_vix_term():
    """KPI box for VIX term structure."""
    vix_ts = dlm.get_vix_term_structure(period="1Y")
    if vix_ts.empty:
        return Styles.kpiboxes("VIX Structure", "N/A", Styles.colorPalette[0])

    ratio = float(vix_ts.iloc[-1])
    if ratio < 0.95:
        text, color = "Contango", Styles.strongGreen
    elif ratio < 1.0:
        text, color = "Mild Contango", Styles.colorPalette[1]
    elif ratio < 1.05:
        text, color = "Flat", Styles.colorPalette[3]
    else:
        text, color = "Backwardation", Styles.strongRed

    ref_vix = dlm.get_reference_values("vix")
    ref_vix3m = dlm.get_reference_values("vix3m")
    ref_label = f"VIX: {ref_vix['current']:.1f}  3M: {ref_vix3m['current']:.1f}"
    return Styles.kpiboxes_ref("VIX Structure", text, color, ref_label, None)


def _kpi_roc(key="sp500", periods=20):
    """KPI for momentum (Rate of Change)."""
    roc = dlm.get_rate_of_change(key, periods, period_window="1Y")
    label = config.MACRO_NAMES.get(key, key)
    if roc.empty:
        return Styles.kpiboxes(f"{label} ROC", "N/A", Styles.colorPalette[0])

    val = float(roc.iloc[-1])
    color = Styles.strongGreen if val >= 0 else Styles.strongRed
    avg_roc = float(roc.mean())
    ref_label = f"Avg {periods}d ROC: {avg_roc:.1f}%"
    return Styles.kpiboxes_ref(f"{label} Momentum", f"{val:+.1f}%", color,
                                ref_label, None)


def _kpi_slope_trend():
    """KPI for yield curve slope direction."""
    slope = dlm.get_yield_slope_trend(lookback=20, period="1Y")
    trend = slope["trend"]
    change = slope["slope_change"]

    if trend == "steepening":
        text, color = "Steepening", Styles.strongGreen
    elif trend == "flattening":
        text, color = "Flattening", Styles.strongRed
    else:
        text, color = "Stable", Styles.colorPalette[1]

    ref_label = f"20d change: {change:+.3f} pp"
    return Styles.kpiboxes_ref("Slope Trend", text, color, ref_label, None)


def _section_predictive(period):
    """Predictive Signals section."""
    kpis = html.Div([
        _kpi_ma_status("spy", "S&P 500"),
        _kpi_vix_term(),
        _kpi_roc("sp500", 20),
        _kpi_ratio("copper", "gold", "Copper/Gold"),
        _kpi_slope_trend(),
    ], className="kpi-row")

    charts_row1 = html.Div([
        html.Div([
            dcc.Graph(figure=_ma_overlay_chart("spy", period),
                      config={'displayModeBar': False}),
        ], className="card"),
        html.Div([
            dcc.Graph(figure=_vix_term_chart(period),
                      config={'displayModeBar': False}),
        ], className="card"),
    ], className="grid-2")

    charts_row2 = html.Div([
        html.Div([
            dcc.Graph(figure=_roc_chart("sp500", 20, period),
                      config={'displayModeBar': False}),
        ], className="card"),
        html.Div([
            dcc.Graph(figure=_slope_trend_chart(period),
                      config={'displayModeBar': False}),
        ], className="card"),
    ], className="grid-2")

    return html.Div([
        html.Div("Predictive Signals", className="macro-section-title"),
        html.P("Forward-looking indicators based on momentum, moving-average crossovers, "
               "VIX term structure, and structural regime shifts. "
               "A golden cross (50 DMA crossing above 200 DMA) signals a new uptrend; "
               "VIX backwardation warns of imminent volatility.",
               className="macro-section-desc"),
        kpis, charts_row1, charts_row2,
    ])


# ─────────────────────────────────────────────
# Signal panel
# ─────────────────────────────────────────────

def _gauge_bar(score, color, height="8px"):
    """Horizontal bar gauge: left = −100 (bearish), right = +100 (bullish)."""
    # Map score from [-100, +100] to [0%, 100%]
    pct = max(0, min(100, (score + 100) / 2))
    return html.Div([
        html.Div(style={
            "width": f"{pct}%",
            "height": height,
            "backgroundColor": color,
            "borderRadius": "4px",
            "transition": "width 0.4s ease",
        }),
    ], className="signal-gauge-track")


def _section_bar_row(section):
    """One row in the section breakdown: name, gauge, score, badge."""
    return html.Div([
        html.Span(section["name"], className="signal-section-name"),
        html.Div(_gauge_bar(section["score"], section["color"]),
                 className="signal-section-gauge"),
        html.Span(f"{section['score']:+.0f}", className="signal-section-score"),
        html.Span(section["action"], className="signal-action-badge",
                  style={"backgroundColor": section["color"]}),
    ], className="signal-section-row")


def _signal_panel():
    """Render the Market Signal panel at the top of the macro page."""
    try:
        sig = macroSignal.compute_overall_signal()
    except Exception:
        return html.Div()  # Fail silently — don't break the page

    # ── Left column: overall score ──
    score_sign = "+" if sig["score"] >= 0 else ""
    left = html.Div([
        html.Div("Overall", className="signal-overall-label"),
        _gauge_bar(sig["score"], sig["color"], height="10px"),
        html.Div([
            html.Span(sig["action"], className="signal-action-badge signal-action-lg",
                      style={"backgroundColor": sig["color"]}),
            html.Span(f"{score_sign}{sig['score']:.0f} / 100",
                      className="signal-overall-score"),
        ], className="signal-overall-row"),
    ], className="signal-panel-left")

    # ── Right column: section breakdown ──
    right = html.Div([
        html.Div("Section Breakdown", className="signal-breakdown-label"),
    ] + [_section_bar_row(s) for s in sig["sections"]],
        className="signal-panel-right")

    # ── Contributors ──
    bullish_items = ", ".join(
        f"{name} ({score:+.0f})" for name, score in sig["top_bullish"]
    ) if sig["top_bullish"] else "—"
    bearish_items = ", ".join(
        f"{name} ({score:+.0f})" for name, score in sig["top_bearish"]
    ) if sig["top_bearish"] else "—"

    contributors = html.Div([
        html.Div([
            html.Span("\u25B2 Bullish: ", style={"color": Styles.strongGreen, "fontWeight": "600"}),
            html.Span(bullish_items),
        ], className="signal-contributor-line"),
        html.Div([
            html.Span("\u25BC Bearish: ", style={"color": Styles.strongRed, "fontWeight": "600"}),
            html.Span(bearish_items),
        ], className="signal-contributor-line"),
    ], className="signal-contributors")

    disclaimer = html.P(
        "\u26A0 Not financial advice. Signals are mechanical aggregations of market indicators.",
        className="signal-disclaimer",
    )

    return html.Div([
        html.Div([
            html.Span("\u25C9", className="signal-panel-icon"),
            html.Span(" Market Signal", className="signal-panel-title"),
        ], className="signal-panel-header"),
        html.Div([left, right], className="signal-panel-grid"),
        contributors,
        disclaimer,
    ], className="signal-panel card")


# ─────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────

def layout():
    return html.Div([
        html.H4("Macro Dashboard"),
        html.P("Track macroeconomic indicators, market sentiment, rates, commodities, and crypto.",
               style={"fontSize": "13px", "color": "var(--text-muted, #888)",
                      "margin": "0 0 16px 0"}),

        # Period selector
        dcc.RadioItems(
            id="macro-period",
            options=[
                {"label": "1M", "value": "1M"},
                {"label": "3M", "value": "3M"},
                {"label": "6M", "value": "6M"},
                {"label": "1Y", "value": "1Y"},
                {"label": "5Y", "value": "5Y"},
            ],
            value="1Y",
            className="period-selector",
            inline=True,
        ),

        # Content rendered by callback
        dcc.Loading(
            html.Div(id="macro-content", children=html.Div([
                Styles.skeleton_kpis(4),
                Styles.skeleton_chart(),
                Styles.skeleton_kpis(4),
                Styles.skeleton_chart(),
            ])),
            type="dot",
        ),
    ])


# ─────────────────────────────────────────────
# Callbacks
# ─────────────────────────────────────────────

def register_callbacks(app):
    @app.callback(
        Output("macro-content", "children"),
        [Input("macro-period", "value")]
    )
    def update_macro_dashboard(period):
        period = period or "1Y"

        df = dlm.load_macro_data()
        if df.empty:
            return html.Div([
                html.P("No macro data available. Click Refresh to fetch data.",
                       style={"fontStyle": "italic", "color": "var(--text-muted, #888)",
                              "padding": "40px 0", "textAlign": "center"}),
            ])

        return html.Div([
            _signal_panel(),
            _section_sentiment(period),
            _section_rates(period),
            _section_equities(period),
            _section_commodities(period),
            _section_crypto(period),
            _section_predictive(period),
        ])
