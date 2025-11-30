from dash import dcc, html
import Styles
import dataLoadRealEstate as dlre

def render_page_content():

    starting_value = 350000
    growth_rate = 0.03
    costs = 1200 * 12
    income = 1700 * 12
    years = 20

    df_real_estate = dlre.real_estate_projection(
        starting_value=starting_value,
        growth_rate=growth_rate,
        costs=costs,
        income=income,
        years=years
    )
    return html.Div([
        html.Hr(),
        html.Div([
            Styles.kpiboxes(f'Starting Value:',
                            starting_value,
                            Styles.colorPalette[0]),
            Styles.kpiboxes(f'Annual Growth Rate:',
                            growth_rate,
                            Styles.colorPalette[1]),
            Styles.kpiboxes(f'Annual Income:',
                            income,
                            Styles.colorPalette[2]),
            Styles.kpiboxes(f'Annual Costs:',
                            costs,
                            Styles.colorPalette[3]),
        ]),
        html.Hr(),
        html.Div([''], style=Styles.FILLER()),
        html.Div([
            dcc.Graph(
                id='real-estate-bar-chart',
                figure={
                    'data': [
                        # Costs - positioned at x - 0.4 (left)
                        {
                            'x': df_real_estate.index.tolist(),
                            'y': df_real_estate['costs'].tolist(),
                            'type': 'bar',
                            'name': 'Costs',
                            'width': 0.25,
                            'marker': {'color': 'red'}
                        },
                        # Income - positioned at x + 0.4 (middle)
                        {
                            'x': df_real_estate.index.tolist(),
                            'y': df_real_estate['income'].tolist(),
                            'type': 'bar',
                            'name': 'Income',
                            'width': 0.25,
                            'marker': {'color': 'green'}
                        },
                        # Asset Value - positioned at x 0 (right, secondary axis)
                        {
                            'x': df_real_estate.index.tolist(),
                            'y': df_real_estate['asset_value_with_appreciation'].tolist(),
                            'type': 'bar',
                            'name': 'Asset Value',
                            'width': 0.25,
                            'marker': {'color': Styles.colorPalette[0]}
                        },
                    ],
                    'layout': {
                        'title': 'Real Estate Projection Over Time',
                        'xaxis': {'title': 'Year'},
                        'yaxis': {
                            'title': 'Costs & Income (CHF)',
                            'side': 'left'
                        },
                        'margin': {'t': 40, 'b': 40, 'l': 40, 'r': 40},
                    }
                }
            )

        ], style=Styles.STYLE(100))
    ])
