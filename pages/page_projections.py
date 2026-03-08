from dash import dcc, html, Input, Output
import Styles
import dataTransformationProjections as dtp
import user_settings


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

        html.Div(id="proj-kpis"),
        html.Hr(),
        html.Div([
            dcc.Loading(
                dcc.Graph(id='proj-monte-carlo-chart'),
                type="circle",
            )
        ], className="card", style=Styles.STYLE(100))
    ])


def register_callbacks(app):
    @app.callback(
        [Output("proj-monte-carlo-chart", "figure"),
         Output("proj-kpis", "children")],
        [Input("proj-expected-return", "value"),
         Input("proj-volatility", "value"),
         Input("proj-time-horizon", "value")]
    )
    def update_projection(expected_return, volatility, time_horizon):
        runs = 1000
        er = expected_return / 100.0
        vol = volatility / 100.0

        monte_carlo_df = dtp.monte_carlo_portfolio_simulation(runs, er, vol, time_horizon)
        years = monte_carlo_df.index.tolist()

        # Compute percentile bands
        percentiles = {}
        for p in [10, 25, 50, 75, 90]:
            percentiles[p] = monte_carlo_df.quantile(p / 100, axis=1)

        # FIRE probability
        budget = user_settings.get("budget", {}) or {}
        exp = budget.get("expenses", {}) or {}
        annual_expenses = sum(v for v in exp.values() if isinstance(v, (int, float))) * 12
        fire_number = annual_expenses / 0.04 if annual_expenses > 0 else 0

        final_values = monte_carlo_df.iloc[-1]
        fire_prob = (final_values >= fire_number).sum() / runs * 100 if fire_number > 0 else 0

        median_final = percentiles[50].iloc[-1]
        p10_final = percentiles[10].iloc[-1]
        p90_final = percentiles[90].iloc[-1]

        # KPIs
        kpis = html.Div([
            Styles.kpiboxes("Median Final Value", f"{median_final:,.0f}", Styles.colorPalette[0]),
            Styles.kpiboxes("10th Percentile", f"{p10_final:,.0f}", Styles.strongRed),
            Styles.kpiboxes("90th Percentile", f"{p90_final:,.0f}", Styles.strongGreen),
            Styles.kpiboxes("FIRE Probability", f"{fire_prob:.0f}%",
                            Styles.strongGreen if fire_prob >= 80 else Styles.colorPalette[3]),
        ])

        # Build percentile band traces
        traces = [
            # 10th-90th percentile band (light)
            {
                'x': years,
                'y': percentiles[90].round(0).tolist(),
                'type': 'scatter',
                'mode': 'lines',
                'line': {'width': 0},
                'showlegend': False,
                'name': '90th',
                'hoverinfo': 'skip',
            },
            {
                'x': years,
                'y': percentiles[10].round(0).tolist(),
                'type': 'scatter',
                'mode': 'lines',
                'fill': 'tonexty',
                'fillcolor': 'rgba(55,63,81,0.12)',
                'line': {'width': 0},
                'name': '10th-90th Percentile',
                'hoverinfo': 'skip',
            },
            # 25th-75th percentile band (darker)
            {
                'x': years,
                'y': percentiles[75].round(0).tolist(),
                'type': 'scatter',
                'mode': 'lines',
                'line': {'width': 0},
                'showlegend': False,
                'name': '75th',
                'hoverinfo': 'skip',
            },
            {
                'x': years,
                'y': percentiles[25].round(0).tolist(),
                'type': 'scatter',
                'mode': 'lines',
                'fill': 'tonexty',
                'fillcolor': 'rgba(55,63,81,0.25)',
                'line': {'width': 0},
                'name': '25th-75th Percentile',
                'hoverinfo': 'skip',
            },
            # Median line (bold)
            {
                'x': years,
                'y': percentiles[50].round(0).tolist(),
                'type': 'scatter',
                'mode': 'lines+markers+text',
                'name': 'Median (50th)',
                'line': {'color': Styles.colorPalette[0], 'width': 3},
                'marker': {'size': 1},
                'text': [
                    f"{int(val):,}" if (year % 5 == 0 and year != 0) else ""
                    for year, val in zip(years, percentiles[50])
                ],
                'textposition': 'top left',
            },
        ]

        # Add FIRE number line if set
        if fire_number > 0:
            traces.append({
                'x': years,
                'y': [fire_number] * len(years),
                'type': 'scatter',
                'mode': 'lines',
                'name': f'FIRE Number ({fire_number:,.0f})',
                'line': {'color': Styles.strongRed, 'dash': 'dash', 'width': 2},
            })

        figure = {
            'data': traces,
            'layout': Styles.graph_layout(
                title=f'Monte Carlo Simulation ({runs} runs, {expected_return}% return, {volatility}% vol)',
                xaxis={'title': 'Year', 'range': [0, time_horizon]},
                yaxis={'title': 'Portfolio Value'},
                hovermode='x unified',
            ),
        }
        return figure, kpis
