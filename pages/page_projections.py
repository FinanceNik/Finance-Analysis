from dash import dcc, html, Input, Output
import Styles
import dataTransformationProjections as dtp


def layout():
    return html.Div([
        html.Hr(),
        html.H4("Monte Carlo Portfolio Simulation"),
        html.Div([
            html.Div([
                html.Label("Expected Annual Return (%)"),
                dcc.Slider(
                    id="proj-expected-return",
                    min=2, max=15, step=0.5, value=8,
                    marks={i: f"{i}%" for i in range(2, 16, 2)},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ], style={"width": "30%", "display": "inline-block", "padding": "10px 20px"}),

            html.Div([
                html.Label("Annual Volatility (%)"),
                dcc.Slider(
                    id="proj-volatility",
                    min=5, max=40, step=1, value=18,
                    marks={i: f"{i}%" for i in range(5, 41, 5)},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ], style={"width": "30%", "display": "inline-block", "padding": "10px 20px"}),

            html.Div([
                html.Label("Time Horizon (years)"),
                dcc.Slider(
                    id="proj-time-horizon",
                    min=5, max=40, step=5, value=20,
                    marks={i: f"{i}y" for i in range(5, 41, 5)},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ], style={"width": "30%", "display": "inline-block", "padding": "10px 20px"}),
        ], style={"marginBottom": "20px"}),

        html.Div([
            dcc.Loading(
                dcc.Graph(id='proj-monte-carlo-chart'),
                type="circle",
            )
        ], style=Styles.STYLE(100))
    ])


def register_callbacks(app):
    @app.callback(
        Output("proj-monte-carlo-chart", "figure"),
        [Input("proj-expected-return", "value"),
         Input("proj-volatility", "value"),
         Input("proj-time-horizon", "value")]
    )
    def update_projection(expected_return, volatility, time_horizon):
        runs = 200
        er = expected_return / 100.0
        vol = volatility / 100.0

        monte_carlo_df = dtp.monte_carlo_portfolio_simulation(runs, er, vol, time_horizon)

        traces = [
            {
                'x': monte_carlo_df.index.tolist(),
                'y': monte_carlo_df[run].tolist(),
                'type': 'line',
                'name': run,
                'line': {'color': 'lightgrey'},
                'showlegend': False
            } for run in monte_carlo_df.columns
        ] + [
            {
                'x': monte_carlo_df.index.tolist(),
                'y': monte_carlo_df.mean(axis=1).tolist(),
                'type': 'line',
                'name': 'Average',
                'line': {'color': Styles.colorPalette[0], 'width': 4},
                'mode': 'lines+markers+text',
                'text': [
                    f"{int(val):,}" if (year % 5 == 0 and year != 0) else ""
                    for year, val in zip(
                        monte_carlo_df.index.tolist(),
                        monte_carlo_df.mean(axis=1)
                    )
                ],
                'textposition': 'top left',
                'showlegend': False
            }
        ]

        figure = {
            'data': traces,
            'layout': {
                'title': f'Monte Carlo Simulation ({runs} runs, {expected_return}% return, {volatility}% vol)',
                'xaxis': {'title': 'Year', 'range': [0, time_horizon]},
                'yaxis': {
                    'title': 'Portfolio Value',
                    'range': [0, monte_carlo_df.mean(axis=1).max() * 2]
                },
                'margin': {'t': 40, 'b': 40, 'l': 60, 'r': 40},
            }
        }
        return figure
