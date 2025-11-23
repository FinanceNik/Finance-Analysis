import Styles
import dataLoadPositions as dlp
from dash import dcc, html

def render_page_content():
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
        html.Hr(),
        html.Div([''], style=Styles.FILLER()),
        html.Div([
            html.H4(f"{dlp.currentYear}"),
            dcc.Graph(
                id='Asset Type Distribution',
                figure={
                    'data': [{
                        'type': 'pie',
                        'labels': dlp.allocation_by_asset_type()['asset_type'].tolist(),
                        'values': dlp.allocation_by_asset_type()['weight'].tolist(),
                        'textinfo': 'label+percent',
                        'hoverinfo': 'label+value+percent',
                        'marker': {'colors': Styles.colorPalette},  # optionally use your palette
                    }],
                    'layout': {
                        'title': f'Asset Type Allocation in {dlp.currentYear}',
                        'margin': {'t': 30, 'b': 30, 'l': 30, 'r': 30},
                    }
                }
            )
        ], style=Styles.STYLE(46)),
        html.Div([''], style=Styles.FILLER()),
        html.Div([
            html.H4(f"{dlp.currentYear}"),
            dcc.Graph(
                id='Geography Allocation Distribution',
                figure={
                    'data': [{
                        'type': 'pie',
                        'labels': dlp.allocation_by_geography()['geography'].tolist(),
                        'values': dlp.allocation_by_geography()['weight'].tolist(),
                        'textinfo': 'label+percent',
                        'hoverinfo': 'label+value+percent',
                        'marker': {'colors': Styles.colorPalette},  # optional color palette
                    }],
                    'layout': {
                        'title': f'Asset Allocation by Geography in {dlp.currentYear}',
                        'margin': {'t': 30, 'b': 30, 'l': 30, 'r': 30},
                    }
                }
            )
        ], style=Styles.STYLE(46))

    ])

