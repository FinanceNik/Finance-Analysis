import Styles
import dataLoadPositions as dlp
import fetchAPI as fapi
from dash import dcc, html
import pandas as pd

def render_page_content():
    df = pd.read_csv("data/historical_data.csv")
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
        html.Hr(),
        html.Div([
            dcc.Graph(
                id='monte-carlo-portfolio-simulation',
                figure={
                    'data': [
                        {
                            'x': df.index.tolist(),
                            'y': df[run].tolist(),
                            'type': 'scatter',
                            'mode': 'markers',
                            'marker': {'size': 3, 'color': Styles.colorPalette[3]},
                            'name': run,
                            'showlegend': True
                        } for run in df.columns
                    ],
                    'layout': {
                        'title': 'Monte Carlo Simulation Runs',
                        'xaxis': {'title': 'Year'},
                        'yaxis': {'title': 'Portfolio Value'},
                        'margin': {'t': 40, 'b': 40, 'l': 40, 'r': 40},
                    }
                }
            )
        ], style=Styles.STYLE(100))

    ])

