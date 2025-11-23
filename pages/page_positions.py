import Styles
import dataLoadPositions as dlp
import fetchAPI as fapi
from dash import dcc, html
import pandas as pd

def render_page_content():
    for ticker in pd.read_csv("data/historical_data.csv").columns:
        y_values = pd.read_csv("data/historical_data.csv")[ticker].tolist()
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
        ], style=Styles.STYLE(46)),
        html.Div([
            dcc.Graph(
                id='historical_performanace',
                figure={
                    'data': [
                                {
                                    'x': pd.read_csv("data/historical_data.csv").index.tolist(),
                                    'y': pd.read_csv("data/historical_data.csv")[run],
                                    'type': 'line',
                                    'name': run,
                                    'line': {'color': Styles.colorPalette[0], 'width': 4},
                                    'showlegend': False
                                } for run in pd.read_csv("data/historical_data.csv").columns
                            ],
                    'layout': {
                        'title': 'Historical Performanace',
                        'xaxis': {'title': 'Year'},
                        'yaxis': {'title': 'Portfolio Value'},
                        'margin': {'t': 40, 'b': 40, 'l': 40, 'r': 40},
                    }
                }
            )
        ], style=Styles.STYLE(100))
    ])

