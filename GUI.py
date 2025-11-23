import dash_bootstrap_components as dbc
import Styles
import dash
from dash.dependencies import Input, Output
from dash import dcc, html
import dataLoadPositions as dlp
from pages import page_positions, page_transactions, page_about, page_projections

basePath = ''
app = dash.Dash(__name__, suppress_callback_exceptions=True,
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                url_base_pathname='/', assets_folder='assets')

sidebar = html.Div(
    [
        html.H1(f"Your {dlp.currentYear}\n in Review", style={'fontSize': '36px', 'fontWeight': 'bold'}),
        html.Hr(style={'borderColor': Styles.greys[3]}),
        # html.H2("Section", className="lead", style={'fontSize': '28px'}),
        dbc.Switch(
            id="theme-switch",
            label="Dark mode",
            value=False,
        ),
        html.Hr(style={'borderColor': Styles.greys[3]}),
        dbc.Nav(
            [
                dbc.NavLink("Positions", href=f"{basePath}/", active="exact"),
                dbc.NavLink("Transactions", href=f"{basePath}/transactions", active="exact"),
                dbc.NavLink("Projections", href=f"{basePath}/projections", active="exact"),
                dbc.NavLink("About This App", href=f"{basePath}/about", active="exact"),
            ],
            vertical=True,
            pills=True,
        ),
    ],
    style=Styles.SIDEBAR_STYLE,
    id="sidebar"
)

content = html.Div(id="page-content", style=Styles.CONTENT_STYLE)

app.layout = html.Div(
    [dcc.Location(id="url", refresh=True),
     dcc.Store(id="theme-store", storage_type='session'),
     sidebar,
     content
     ], id="main-layout"
)


@app.callback(Output("page-content", "children"), [Input("url", "pathname")])
def render_page_content(pathname):
    if pathname == f"{basePath}/":
        return page_positions.render_page_content()

    elif pathname == f"{basePath}/transactions":
        return page_transactions.render_page_content()

    elif pathname == f"{basePath}/projections":
        return page_projections.render_page_content()

    elif pathname == f"{basePath}/about":
        return page_about.render_page_content()


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)
