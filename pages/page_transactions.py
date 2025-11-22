import Styles
import dataLoadTransactions as dlt
from dash import dcc, html

def render_page_content():
    value = ""

    return html.Div([
        html.Hr(),
        html.Div([
            Styles.kpiboxes(f'Total Value:',
                            dlp.portfolio_total_value(),
                            Styles.colorPalette[0]),
            Styles.kpiboxes(f'Total Pur.-Cost:',
                            dlp.portfolio_cost_basis(),
                            Styles.colorPalette[1]),
            Styles.kpiboxes(f'Total Unr. Gains:',
                            dlp.portfolio_unrealized_pnl(),
                            Styles.colorPalette[2]),
            Styles.kpiboxes(f'Total % Return:',
                            dlp.portfolio_return_pct(),
                            Styles.colorPalette[3]),
        ]),
        html.Hr()
    ])

