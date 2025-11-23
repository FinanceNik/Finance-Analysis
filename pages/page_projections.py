from dash import dcc, html
import Styles
import dataTransformationProjections as dtp

def render_page_content(runs=200, expected_return=0.08, volatility=0.18, time_horizon=20):
    monte_carlo_df = dtp.monte_carlo_portfolio_simulation(runs, expected_return, volatility, time_horizon)
    return html.Div([
        html.Div([
            html.H4("Monte Carlo Portfolio Simulation: Next 10 Years"),
            dcc.Graph(
                id='monte-carlo-portfolio-simulation',
                figure={
                    'data': [
                                # All runs as light grey lines
                                {
                                    'x': monte_carlo_df.index.tolist(),
                                    'y': monte_carlo_df[run].tolist(),
                                    'type': 'line',
                                    'name': run,
                                    'line': {'color': 'lightgrey'},
                                    'showlegend': False
                                } for run in monte_carlo_df.columns
                            ] + [
                                # Average line with data labels every 5 years
                                {
                                    'x': monte_carlo_df.index.tolist(),
                                    'y': monte_carlo_df.mean(axis=1).tolist(),
                                    'type': 'line',
                                    'name': 'Average',
                                    'line': {'color': Styles.colorPalette[0], 'width': 4},
                                    'mode': 'lines+markers+text',
                                    'text': [f"{int(val):,}" if (year % 5 == 0 and year != 0) else ""
                                             for year, val in zip(monte_carlo_df.index.tolist(),
                                                                  monte_carlo_df.mean(axis=1))
                                        ],
                                    'textposition': 'top left',
                                    'showlegend': False
                                }
                            ],
                    'layout': {
                        'title': 'Monte Carlo Simulation Runs',
                        'xaxis': {'title': 'Year',
                                  'range': [0, time_horizon]},
                        'yaxis': {
                            'title': 'Portfolio Value',
                            'range': [0, monte_carlo_df.mean(axis=1).max() * 2]
                        },
                        'margin': {'t': 40, 'b': 40, 'l': 40, 'r': 40},
                    }
                }
            )
        ], style=Styles.STYLE(100))
    ])
