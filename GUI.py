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
                   page_networth, page_goals, page_rebalancing, page_taxlots,
                   page_budget, page_dashboard, page_scenarios, page_income,
                   page_currency, page_dividends)
import fetchAPI

fetchAPI.fetch_historical_data_yfinance()

basePath = ''
app = dash.Dash(__name__, suppress_callback_exceptions=True,
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                url_base_pathname='/', assets_folder='assets')


def _nav_section(title, links):
    """Create a labeled navigation section."""
    return html.Div([
        html.Div(title, className="nav-section-label"),
        dbc.Nav(links, vertical=True, pills=True),
    ], style={"marginBottom": "8px"})


sidebar = html.Div(
    [
        html.H1("Wealth\nAnalysis"),
        html.Hr(),
        dbc.Switch(
            id="theme-switch",
            label="Dark mode",
            value=False,
        ),
        html.Div([
            html.Button("Refresh Data", id="refresh-btn", className="sidebar-btn"),
            html.Button("Export PDF", id="export-pdf-btn", className="sidebar-btn-outline"),
            html.Div(id="refresh-status", style={
                "fontSize": "11px", "color": "var(--text-muted)",
                "marginTop": "4px", "textAlign": "center",
            }),
        ], style={"marginTop": "10px"}),
        html.Hr(),
        _nav_section("Overview", [
            dbc.NavLink("Dashboard", href=f"{basePath}/", active="exact"),
            dbc.NavLink("Net Worth", href=f"{basePath}/net-worth", active="exact"),
        ]),
        _nav_section("Portfolio", [
            dbc.NavLink("Positions", href=f"{basePath}/positions", active="exact"),
            dbc.NavLink("Analytics", href=f"{basePath}/analytics", active="exact"),
            dbc.NavLink("Transactions", href=f"{basePath}/transactions", active="exact"),
            dbc.NavLink("Currency", href=f"{basePath}/currency", active="exact"),
            dbc.NavLink("Tax Lots", href=f"{basePath}/tax-lots", active="exact"),
            dbc.NavLink("Rebalancing", href=f"{basePath}/rebalancing", active="exact"),
        ]),
        _nav_section("Income", [
            dbc.NavLink("Budget", href=f"{basePath}/budget", active="exact"),
            dbc.NavLink("Income Statement", href=f"{basePath}/income-statement", active="exact"),
            dbc.NavLink("Dividends", href=f"{basePath}/dividends", active="exact"),
        ]),
        _nav_section("Planning", [
            dbc.NavLink("Projections", href=f"{basePath}/projections", active="exact"),
            dbc.NavLink("Scenarios", href=f"{basePath}/scenarios", active="exact"),
            dbc.NavLink("Real Estate", href=f"{basePath}/real-estate", active="exact"),
            dbc.NavLink("Goals", href=f"{basePath}/goals", active="exact"),
        ]),
        html.Hr(),
        dbc.Nav([
            dbc.NavLink("About", href=f"{basePath}/about", active="exact"),
        ], vertical=True, pills=True),
    ],
    style=Styles.SIDEBAR_STYLE,
    id="sidebar"
)

content = html.Div(id="page-content", style=Styles.CONTENT_STYLE)

app.layout = html.Div(
    [dcc.Location(id="url", refresh=False),
     dcc.Store(id="theme-store", storage_type='session'),
     html.Button("\u2630", id="mobile-menu-btn", className="mobile-menu-btn"),
     sidebar,
     content
     ], id="main-layout"
)


# --- Dark mode toggle ---
@app.callback(
    [Output("sidebar", "style"),
     Output("page-content", "style"),
     Output("main-layout", "className"),
     Output("theme-store", "data")],
    [Input("theme-switch", "value")]
)
def toggle_dark_mode(dark_mode):
    if dark_mode:
        return Styles.SIDEBAR_STYLE_DARK, Styles.CONTENT_STYLE_DARK, "dark-mode", True
    return Styles.SIDEBAR_STYLE, Styles.CONTENT_STYLE, "", False


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


# --- Data refresh ---
@app.callback(
    Output("refresh-status", "children"),
    [Input("refresh-btn", "n_clicks")],
    prevent_initial_call=True
)
def refresh_data(n_clicks):
    if not n_clicks:
        return ""
    dlp.fetch_data.cache_clear()
    dlt.ingest_transactions.cache_clear()
    fetchAPI.fetch_historical_data_yfinance()
    return f"Refreshed {datetime.now().strftime('%H:%M:%S')}"


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


# --- Page routing ---
@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def render_page_content(pathname):
    if pathname == f"{basePath}/":
        return page_dashboard.layout()

    elif pathname == f"{basePath}/positions":
        return page_positions.layout()

    elif pathname == f"{basePath}/transactions":
        return page_transactions.render_page_content()

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

    elif pathname == f"{basePath}/tax-lots":
        return page_taxlots.layout()

    elif pathname == f"{basePath}/scenarios":
        return page_scenarios.layout()

    elif pathname == f"{basePath}/income-statement":
        return page_income.layout()

    elif pathname == f"{basePath}/currency":
        return page_currency.layout()

    elif pathname == f"{basePath}/dividends":
        return page_dividends.layout()

    elif pathname == f"{basePath}/about":
        return page_about.render_page_content()


# --- Register callbacks from pages ---
page_projections.register_callbacks(app)
page_realEstate.register_callbacks(app)
page_positions.register_callbacks(app)
page_networth.register_callbacks(app)
page_goals.register_callbacks(app)
page_rebalancing.register_callbacks(app)
page_budget.register_callbacks(app)
page_taxlots.register_callbacks(app)
page_scenarios.register_callbacks(app)
page_transactions.register_callbacks(app)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=False)
