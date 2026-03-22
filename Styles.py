from dash import dcc, html

# ── Color palette ──
greys = ['#2b2b2b', '#3b3b3b', '#cfcfcf', '#f0f0f0']

colorPalette = {
    0: ['#495C83', '#7A86B6', '#A8A4CE', '#C8B6E2'],
    1: ['#373F51', '#008DD5', '#F56476', '#E43F6F'],
    2: ['#2A4747', '#439775', '#48BF84', '#E0BAD7'],
}

purple_list = colorPalette[1] + colorPalette[0]
colorPalette = colorPalette[1]

strongGreen = '#34c759'
strongRed = '#ff3b30'

# ── Transparent graph background (adapts to CSS theme) ──
GRAPH_BG = 'rgba(0,0,0,0)'

# ── Default graph layout applied to all figures ──
GRAPH_LAYOUT = {
    'paper_bgcolor': GRAPH_BG,
    'plot_bgcolor': GRAPH_BG,
    'font': {'family': '-apple-system, BlinkMacSystemFont, system-ui, sans-serif',
             'size': 13},
    'margin': {'t': 40, 'b': 40, 'l': 50, 'r': 30},
}


def graph_layout(**overrides):
    """Return a graph layout dict with transparent bg + any overrides."""
    layout = {**GRAPH_LAYOUT}
    layout.update(overrides)
    # Deep-merge margin if provided
    if 'margin' in overrides:
        m = {**GRAPH_LAYOUT.get('margin', {})}
        m.update(overrides['margin'])
        layout['margin'] = m
    return layout


# ── Sidebar / Content styles (minimal inline — CSS handles the rest) ──
SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "13rem",
    "padding": "1.5rem 1rem",
}

SIDEBAR_STYLE_DARK = {**SIDEBAR_STYLE}

CONTENT_STYLE = {
    "marginLeft": "16rem",
    "marginRight": "2rem",
    "padding": "1.5rem 1.5rem",
}

CONTENT_STYLE_DARK = {**CONTENT_STYLE}


# ── KPI boxes (clean HTML, no DataTable hack) ──
# ── Skeleton loading placeholders ──
def skeleton_kpis(count=4):
    """Shimmer skeleton row matching KPI box layout."""
    return html.Div([
        html.Div(
            html.Div(className="skeleton-line skeleton-kpi"),
            className="kpi-box",
        ) for _ in range(count)
    ], className="kpi-row")


def skeleton_chart(height="300px"):
    """Shimmer skeleton matching a chart card."""
    return html.Div(
        html.Div(className="skeleton-line skeleton-chart",
                 style={"height": height}),
        className="card", style={"padding": "16px"},
    )


def skeleton_table(rows=5):
    """Shimmer skeleton matching a data table."""
    return html.Div([
        html.Div(className="skeleton-line",
                 style={"height": "20px", "width": "100%", "marginBottom": "12px"}),
    ] + [
        html.Div(className="skeleton-line skeleton-table-row",
                 style={"width": f"{85 + (i % 3) * 5}%"})
        for i in range(rows)
    ], className="card", style={"padding": "16px"})


def kpiboxes(label_text, value, color):
    return html.Div(
        html.Div([
            html.Div(label_text, className="kpi-label"),
            html.Div(str(value), className="kpi-value"),
        ], className="kpi-inner", style={"backgroundColor": color}),
        className="kpi-box",
    )


def kpiboxes_spark(label_text, value, color, data_points=None):
    """KPI box with an optional SVG sparkline.
    data_points: list of numeric values to render as a mini line chart.
    """
    spark = html.Div()
    if data_points and len(data_points) >= 2:
        # Normalize to SVG coordinates (80 wide, 24 tall)
        vals = [float(v) for v in data_points if v is not None]
        if vals:
            mn, mx = min(vals), max(vals)
            rng = mx - mn if mx != mn else 1
            w, h = 80, 24
            pts = []
            for i, v in enumerate(vals):
                x = round(i / (len(vals) - 1) * w, 1)
                y = round(h - (v - mn) / rng * h, 1)
                pts.append(f"{x},{y}")
            polyline = f'<polyline points="{" ".join(pts)}" fill="none" stroke="rgba(255,255,255,0.6)" stroke-width="1.5" />'
            svg = f'<svg viewBox="0 0 {w} {h}" style="width:80px;height:24px;margin-top:4px;">{polyline}</svg>'
            spark = dcc.Markdown(
                f'<div style="margin-top:4px">{svg}</div>',
                dangerously_allow_html=True,
                style={"margin": 0, "padding": 0, "lineHeight": 0},
            )

    return html.Div(
        html.Div([
            html.Div(label_text, className="kpi-label"),
            html.Div(str(value), className="kpi-value"),
            spark,
        ], className="kpi-inner", style={"backgroundColor": color}),
        className="kpi-box",
    )


def kpiboxes_ref(label_text, value, color, ref_label="", ref_pct=None):
    """KPI box with a reference comparison line.

    ref_label: e.g. "52w avg: 16.2"
    ref_pct:   e.g. +14.3 (positive = up arrow green, negative = down arrow red)
    """
    ref_children = []
    if ref_label:
        ref_children.append(html.Span(ref_label, className="kpi-ref-label"))
    if ref_pct is not None:
        arrow = "\u25B2" if ref_pct >= 0 else "\u25BC"
        pct_color = strongGreen if ref_pct >= 0 else strongRed
        ref_children.append(html.Span(
            f" {arrow}{abs(ref_pct):.1f}%",
            style={"color": pct_color, "fontWeight": "600"},
        ))

    ref_line = html.Div(ref_children, className="kpi-ref") if ref_children else html.Div()

    return html.Div(
        html.Div([
            html.Div(label_text, className="kpi-label"),
            html.Div(str(value), className="kpi-value"),
            ref_line,
        ], className="kpi-inner", style={"backgroundColor": color}),
        className="kpi-box",
    )
