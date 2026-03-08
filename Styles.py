from dash import html

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


# ── Card wrapper ──
def STYLE(width):
    """Return inline style for a card-like container."""
    return {
        'width': f'{width}%',
        'display': 'inline-block',
        'verticalAlign': 'top',
        'padding': '16px',
    }


def FILLER():
    return {
        'width': '2%',
        'display': 'inline-block',
        'padding': '5px',
    }


# ── KPI boxes (clean HTML, no DataTable hack) ──
def kpiboxes(label_text, value, color):
    return html.Div(
        html.Div([
            html.Div(label_text, className="kpi-label"),
            html.Div(str(value), className="kpi-value"),
        ], className="kpi-inner", style={"backgroundColor": color}),
        className="kpi-box",
    )
