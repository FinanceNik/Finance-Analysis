import json
import dash_bootstrap_components as dbc
import Styles
import dash
from dash.dependencies import Input, Output, State
from dash import dcc, html
from datetime import datetime
import dataLoadPositions as dlp
import dataLoadTransactions as dlt
from pages import (page_positions, page_transactions, page_about,  # noqa: E501
                   page_projections, page_realEstate, page_analytics,
                   page_networth, page_goals, page_rebalancing,
                   page_budget, page_dashboard, page_scenarios, page_income,
                   page_dividends, page_macro, page_backtest, page_currency,
                   page_alerts, page_taxloss, page_snapshots)
import fetchAPI
import dataLoadMacro as dlm
import backtestEngine as bte

fetchAPI.fetch_historical_data_yfinance()
fetchAPI.fetch_macro_data()

basePath = ''
app = dash.Dash(__name__, suppress_callback_exceptions=True,
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                url_base_pathname='/', assets_folder='assets')

# ── Page name mapping for breadcrumbs ──
PAGE_MAP = {
    "/": ("Overview", "Dashboard"),
    "/net-worth": ("Overview", "Net Worth"),
    "/positions": ("Portfolio", "Positions"),
    "/analytics": ("Portfolio", "Analytics"),
    "/transactions": ("Portfolio", "Transactions"),
    "/rebalancing": ("Portfolio", "Rebalancing"),
    "/currency": ("Portfolio", "Currency Exposure"),
    "/budget": ("Income", "Budget"),
    "/income-statement": ("Income", "Income Statement"),
    "/dividends": ("Income", "Dividends"),
    "/projections": ("Planning", "Projections"),
    "/scenarios": ("Planning", "Scenarios"),
    "/real-estate": ("Planning", "Real Estate"),
    "/goals": ("Planning", "Goals"),
    "/macro": ("Macro", "Macro Dashboard"),
    "/backtest": ("Macro", "Strategy Backtest"),
    "/alerts": ("Overview", "Alerts"),
    "/snapshots": ("Overview", "Snapshots"),
    "/tax-loss": ("Portfolio", "Tax-Loss Harvesting"),
    "/about": ("", "About"),
}


# ── Sidebar icons ──
_ICONS = {
    "Dashboard": "\u229E", "Net Worth": "\u25CE",
    "Positions": "\u2630", "Analytics": "\u25C6",
    "Transactions": "\u21C4", "Rebalancing": "\u2696", "Currency Exposure": "\u25CB",
    "Budget": "\u2610", "Income Statement": "\u2261",
    "Dividends": "\u2756",
    "Projections": "\u25D0", "Scenarios": "\u26A1",
    "Real Estate": "\u2302", "Goals": "\u25C9",
    "Macro Dashboard": "\u25C9",
    "Strategy Backtest": "\u25B7",
    "Alerts": "\u25B2",
    "Snapshots": "\u25C9",
    "Tax-Loss Harvesting": "\u2702",
    "About": "\u24D8",
}


def _nav_link(label, href):
    """Create a nav link with an icon prefix."""
    icon = _ICONS.get(label, "")
    return dbc.NavLink([
        html.Span(icon, className="nav-icon"), label
    ], href=href, active="exact")


def _nav_section(title, links, section_id):
    """Create a collapsible navigation section with click-to-toggle header."""
    return html.Div([
        html.Div([
            html.Div(title, className="nav-section-label"),
            html.Span("\u25B8", className="nav-section-chevron",
                       id=f"chevron-{section_id}"),
        ], className="nav-section-header", id=f"nav-header-{section_id}"),
        html.Div(
            dbc.Nav(links, vertical=True, pills=True),
            className="nav-section-body",
            id=f"nav-body-{section_id}",
        ),
    ], style={"marginBottom": "8px"})


sidebar = html.Div(
    [
        html.H1("Wealth\nAnalysis"),
        html.Hr(),
        _nav_section("Overview", [
            _nav_link("Dashboard", f"{basePath}/"),
            _nav_link("Net Worth", f"{basePath}/net-worth"),
            _nav_link("Alerts", f"{basePath}/alerts"),
            _nav_link("Snapshots", f"{basePath}/snapshots"),
        ], "overview"),
        _nav_section("Portfolio", [
            _nav_link("Positions", f"{basePath}/positions"),
            _nav_link("Analytics", f"{basePath}/analytics"),
            _nav_link("Transactions", f"{basePath}/transactions"),
            _nav_link("Rebalancing", f"{basePath}/rebalancing"),
            _nav_link("Currency Exposure", f"{basePath}/currency"),
            _nav_link("Tax-Loss Harvesting", f"{basePath}/tax-loss"),
        ], "portfolio"),
        _nav_section("Income", [
            _nav_link("Budget", f"{basePath}/budget"),
            _nav_link("Income Statement", f"{basePath}/income-statement"),
            _nav_link("Dividends", f"{basePath}/dividends"),
        ], "income"),
        _nav_section("Planning", [
            _nav_link("Projections", f"{basePath}/projections"),
            _nav_link("Scenarios", f"{basePath}/scenarios"),
            _nav_link("Real Estate", f"{basePath}/real-estate"),
            _nav_link("Goals", f"{basePath}/goals"),
        ], "planning"),
        _nav_section("Macro", [
            _nav_link("Macro Dashboard", f"{basePath}/macro"),
            _nav_link("Strategy Backtest", f"{basePath}/backtest"),
        ], "macro"),
        dbc.Nav([
            _nav_link("About", f"{basePath}/about"),
        ], vertical=True, pills=True, style={"marginTop": "12px"}),
    ],
    style=Styles.SIDEBAR_STYLE,
    id="sidebar"
)

top_header = html.Div([
    html.Div([
        html.Button("\u2630", id="hamburger-btn", className="hamburger-btn"),
        html.Span(id="breadcrumb", className="breadcrumb-text"),
    ], className="top-header-left"),
    html.Div([
        html.Button("Refresh", id="refresh-btn", className="header-btn"),
        html.Button("Export PDF", id="export-pdf-btn", className="header-btn-outline"),
        html.Span("\u2318K", className="cmd-shortcut-hint", id="cmd-hint",
                   title="Quick navigation"),
        html.Button("\u2600", id="theme-toggle-btn", className="theme-toggle-btn"),
    ], className="top-header-right"),
], className="top-header", id="top-header")

# ── Toast notification ──
refresh_toast = html.Div(
    dbc.Toast(
        id="refresh-toast",
        header="\u2705 Data Refreshed",
        is_open=False,
        duration=3000,
        dismissable=True,
    ),
    className="toast-container",
)

scroll_progress = html.Div(
    html.Div(id="scroll-progress-bar", className="scroll-progress-bar"),
    className="scroll-progress", id="scroll-progress"
)

# ── Command palette data (read by assets/quicknav.js) ──
_palette_data = {href: {"section": sec, "name": name, "icon": _ICONS.get(name, "")}
                 for href, (sec, name) in PAGE_MAP.items()}
cmd_palette_data = html.Div(
    json.dumps(_palette_data), id="cmd-palette-data",
    style={"display": "none"}
)

content = html.Div(id="page-content", style=Styles.CONTENT_STYLE)

app.layout = html.Div(
    [dcc.Location(id="url", refresh=False),
     dcc.Store(id="theme-store", storage_type='session'),
     # Hidden switch preserves existing callback contract
     dbc.Switch(id="theme-switch", value=False, style={"display": "none"}),
     html.Button("\u2630", id="mobile-menu-btn", className="mobile-menu-btn"),
     cmd_palette_data,
     sidebar,
     scroll_progress,
     top_header,
     refresh_toast,
     content
     ], id="main-layout"
)


# --- Dark mode: icon button toggles hidden switch ---
app.clientside_callback(
    """
    function(n_clicks, current_value) {
        if (n_clicks) { return !current_value; }
        return current_value || false;
    }
    """,
    Output("theme-switch", "value"),
    [Input("theme-toggle-btn", "n_clicks")],
    [State("theme-switch", "value")],
    prevent_initial_call=True
)


@app.callback(
    [Output("sidebar", "style"),
     Output("page-content", "style"),
     Output("main-layout", "className"),
     Output("theme-store", "data"),
     Output("theme-toggle-btn", "children")],
    [Input("theme-switch", "value")]
)
def toggle_dark_mode(dark_mode):
    icon = "\u263E" if dark_mode else "\u2600"  # Moon or Sun
    if dark_mode:
        return Styles.SIDEBAR_STYLE_DARK, Styles.CONTENT_STYLE_DARK, "dark-mode", True, icon
    return Styles.SIDEBAR_STYLE, Styles.CONTENT_STYLE, "", False, icon


# --- Breadcrumb ---
@app.callback(
    Output("breadcrumb", "children"),
    [Input("url", "pathname")]
)
def update_breadcrumb(pathname):
    section, page = PAGE_MAP.get(pathname, ("", "Dashboard"))
    if section:
        return [
            html.Span(f"{section}  \u203A  "),
            html.Span(page, className="breadcrumb-page"),
        ]
    return html.Span(page, className="breadcrumb-page")


# --- Collapsible sidebar sections ---
app.clientside_callback(
    """
    function(pathname, n1, n2, n3, n4, n5) {
        var sections = ['overview', 'portfolio', 'income', 'planning', 'macro'];
        var paths = {
            'overview': ['/', '/net-worth', '/alerts', '/snapshots'],
            'portfolio': ['/positions', '/analytics', '/transactions',
                          '/rebalancing', '/currency', '/tax-loss'],
            'income': ['/budget', '/income-statement', '/dividends'],
            'planning': ['/projections', '/scenarios', '/real-estate', '/goals'],
            'macro': ['/macro', '/backtest'],
        };

        var triggered = dash_clientside.callback_context.triggered;
        var clicked_section = null;
        if (triggered && triggered.length > 0) {
            var prop_id = triggered[0].prop_id;
            sections.forEach(function(s) {
                if (prop_id.indexOf('nav-header-' + s) !== -1) {
                    clicked_section = s;
                }
            });
        }

        sections.forEach(function(s) {
            var body = document.getElementById('nav-body-' + s);
            var chevron = document.getElementById('chevron-' + s);
            if (!body || !chevron) return;
            var is_active = paths[s].indexOf(pathname) !== -1;

            if (clicked_section === s) {
                body.classList.toggle('open');
                chevron.classList.toggle('open');
            } else if (clicked_section === null) {
                if (is_active) {
                    body.classList.add('open');
                    chevron.classList.add('open');
                } else {
                    body.classList.remove('open');
                    chevron.classList.remove('open');
                }
            }
        });

        return window.dash_clientside.no_update;
    }
    """,
    Output("nav-body-overview", "className"),
    [Input("url", "pathname"),
     Input("nav-header-overview", "n_clicks"),
     Input("nav-header-portfolio", "n_clicks"),
     Input("nav-header-income", "n_clicks"),
     Input("nav-header-planning", "n_clicks"),
     Input("nav-header-macro", "n_clicks")],
    prevent_initial_call=False
)


# --- Mobile sidebar toggle ---
@app.callback(
    Output("sidebar", "className"),
    [Input("mobile-menu-btn", "n_clicks")],
    [State("sidebar", "className")],
    prevent_initial_call=True
)
def toggle_sidebar(n_clicks, current_class):
    if current_class and "sidebar-open" in current_class:
        return ""
    return "sidebar-open"


# --- Data refresh (toast notification) ---
@app.callback(
    [Output("refresh-toast", "is_open"),
     Output("refresh-toast", "children")],
    [Input("refresh-btn", "n_clicks")],
    prevent_initial_call=True
)
def refresh_data(n_clicks):
    if not n_clicks:
        return False, ""
    dlp.fetch_data.cache_clear()
    dlp.load_historical_data.cache_clear()
    dlt.ingest_transactions.cache_clear()
    dlm.load_macro_data.cache_clear()
    bte.clear_cache()
    fetchAPI.fetch_historical_data_yfinance()
    fetchAPI.fetch_macro_data()
    return True, f"Portfolio data updated at {datetime.now().strftime('%H:%M:%S')}"


# --- PDF export (client-side) ---
app.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks) { window.print(); }
        return '';
    }
    """,
    Output("export-pdf-btn", "title"),
    [Input("export-pdf-btn", "n_clicks")],
    prevent_initial_call=True
)


# --- Hamburger sidebar toggle (responsive) ---
app.clientside_callback(
    """
    function(n) {
        if (n) { document.body.classList.toggle('sidebar-open'); }
        return dash_clientside.no_update;
    }
    """,
    Output("hamburger-btn", "className"),
    Input("hamburger-btn", "n_clicks"),
    prevent_initial_call=True
)


# --- Page routing ---
@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def render_page_content(pathname):
    if pathname == f"{basePath}/":
        return page_dashboard.layout()
    elif pathname == f"{basePath}/positions":
        return page_positions.layout()
    elif pathname == f"{basePath}/transactions":
        return page_transactions.layout()
    elif pathname == f"{basePath}/projections":
        return page_projections.layout()
    elif pathname == f"{basePath}/real-estate":
        return page_realEstate.layout()
    elif pathname == f"{basePath}/analytics":
        return page_analytics.layout()
    elif pathname == f"{basePath}/net-worth":
        return page_networth.layout()
    elif pathname == f"{basePath}/goals":
        return page_goals.layout()
    elif pathname == f"{basePath}/rebalancing":
        return page_rebalancing.layout()
    elif pathname == f"{basePath}/budget":
        return page_budget.layout()
    elif pathname == f"{basePath}/scenarios":
        return page_scenarios.layout()
    elif pathname == f"{basePath}/income-statement":
        return page_income.layout()
    elif pathname == f"{basePath}/dividends":
        return page_dividends.layout()
    elif pathname == f"{basePath}/macro":
        return page_macro.layout()
    elif pathname == f"{basePath}/backtest":
        return page_backtest.layout()
    elif pathname == f"{basePath}/currency":
        return page_currency.layout()
    elif pathname == f"{basePath}/tax-loss":
        return page_taxloss.layout()
    elif pathname == f"{basePath}/alerts":
        return page_alerts.layout()
    elif pathname == f"{basePath}/snapshots":
        return page_snapshots.layout()
    elif pathname == f"{basePath}/about":
        return page_about.layout()


# --- Register callbacks from pages ---
page_projections.register_callbacks(app)
page_realEstate.register_callbacks(app)
page_positions.register_callbacks(app)
page_networth.register_callbacks(app)
page_goals.register_callbacks(app)
page_rebalancing.register_callbacks(app)
page_budget.register_callbacks(app)
page_scenarios.register_callbacks(app)
page_dividends.register_callbacks(app)
page_macro.register_callbacks(app)
page_backtest.register_callbacks(app)
page_alerts.register_callbacks(app)
page_taxloss.register_callbacks(app)
page_snapshots.register_callbacks(app)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=False)
