from dash import dcc, html, Input, Output
import Styles
import dataLoadPositions as dlp
import user_settings


def layout():
    return html.Div([
        html.Hr(),
        html.H4("Scenario Planning"),

        # --- Input sliders ---
        html.Div([
            html.Div([
                html.Label("Additional Monthly Savings"),
                dcc.Slider(
                    id="slider-savings",
                    min=0, max=5000, step=100, value=0,
                    marks={i: f"{i:,}" for i in range(0, 5001, 1000)},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ], style={"width": "24%", "display": "inline-block", "padding": "10px 20px"}),

            html.Div([
                html.Label("Market Return (%)"),
                dcc.Slider(
                    id="slider-return",
                    min=-30, max=30, step=1, value=7,
                    marks={i: f"{i}%" for i in range(-30, 31, 10)},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ], style={"width": "24%", "display": "inline-block", "padding": "10px 20px"}),

            html.Div([
                html.Label("Inflation (%)"),
                dcc.Slider(
                    id="slider-inflation",
                    min=0, max=10, step=0.5, value=1.5,
                    marks={i: f"{i}%" for i in range(0, 11, 2)},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ], style={"width": "24%", "display": "inline-block", "padding": "10px 20px"}),

            html.Div([
                html.Label("Years to Project"),
                dcc.Slider(
                    id="slider-years",
                    min=5, max=40, step=1, value=20,
                    marks={i: f"{i}y" for i in range(5, 41, 5)},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ], style={"width": "24%", "display": "inline-block", "padding": "10px 20px"}),
        ], style={"marginBottom": "20px"}),

        # --- Dynamic KPIs and charts ---
        html.Div(id="scenario-kpis"),
        html.Hr(),
        html.Div(id="scenario-charts"),
    ])


def _hex_to_rgba(hex_color, alpha):
    """Convert hex color to rgba string."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _project_portfolio(start_value, annual_return, annual_contribution, years):
    """Project portfolio value year by year.

    Returns a list of values for year 0 through `years` (inclusive).
    """
    values = [start_value]
    current = start_value
    for _ in range(years):
        current = current * (1 + annual_return / 100) + annual_contribution
        values.append(round(current))
    return values


def _project_crash_scenario(start_value, annual_return, annual_contribution, years):
    """40 % drop in year 1, then recovery at the base return rate."""
    values = [start_value]
    current = start_value
    for yr in range(1, years + 1):
        if yr == 1:
            current = current * 0.60 + annual_contribution
        else:
            current = current * (1 + annual_return / 100) + annual_contribution
        values.append(round(current))
    return values


def register_callbacks(app):
    @app.callback(
        [Output("scenario-kpis", "children"),
         Output("scenario-charts", "children")],
        [Input("slider-savings", "value"),
         Input("slider-return", "value"),
         Input("slider-inflation", "value"),
         Input("slider-years", "value")]
    )
    def update_scenarios(extra_savings, market_return, inflation, years):
        extra_savings = extra_savings or 0
        market_return = market_return or 7
        inflation = inflation if inflation is not None else 1.5
        years = years or 20

        # Current portfolio and budget data
        portfolio = dlp.portfolio_total_value()
        budget = user_settings.get("budget", {})
        inc = budget.get("income", {})
        exp = budget.get("expenses", {})
        total_income = sum(inc.values()) if inc else 0
        total_expenses = sum(exp.values()) if exp else 0
        current_monthly_savings = total_income - total_expenses

        monthly_contribution = current_monthly_savings + extra_savings
        annual_contribution = monthly_contribution * 12

        # FIRE number
        annual_expenses = total_expenses * 12
        fire_number = annual_expenses / 0.04 if annual_expenses > 0 else 0

        year_labels = list(range(0, years + 1))

        # ── Scenario projections ──
        base_values = _project_portfolio(portfolio, market_return, annual_contribution, years)
        optimistic_values = _project_portfolio(portfolio, market_return + 3, annual_contribution, years)
        pessimistic_values = _project_portfolio(portfolio, market_return - 3, annual_contribution, years)
        crash_values = _project_crash_scenario(portfolio, market_return, annual_contribution, years)

        # Inflation-adjusted base values
        real_values = [
            round(v / (1 + inflation / 100) ** yr) for yr, v in enumerate(base_values)
        ]

        projected = base_values[-1]
        real_projected = real_values[-1]
        total_contributed = portfolio + annual_contribution * years
        total_growth = projected - total_contributed

        # ── KPIs ──
        kpis = html.Div([
            Styles.kpiboxes("Projected Portfolio", f"{projected:,.0f}", Styles.colorPalette[0]),
            Styles.kpiboxes("Real Value (After Inflation)", f"{real_projected:,.0f}", Styles.colorPalette[1]),
            Styles.kpiboxes("Total Contributed", f"{total_contributed:,.0f}", Styles.colorPalette[2]),
            Styles.kpiboxes("Total Growth", f"{total_growth:,.0f}",
                            Styles.strongGreen if total_growth >= 0 else Styles.strongRed),
        ])

        # ── Chart 1: Portfolio Projection Scenarios (full width) ──
        scenario_chart = {
            'data': [
                # Optimistic / pessimistic fill cone
                {
                    'x': year_labels,
                    'y': optimistic_values,
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': 'Optimistic',
                    'line': {'color': _hex_to_rgba(Styles.strongGreen, 0.6), 'dash': 'dot'},
                    'showlegend': True,
                },
                {
                    'x': year_labels,
                    'y': pessimistic_values,
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': 'Pessimistic',
                    'fill': 'tonexty',
                    'fillcolor': _hex_to_rgba(Styles.colorPalette[0], 0.10),
                    'line': {'color': _hex_to_rgba(Styles.strongRed, 0.6), 'dash': 'dot'},
                    'showlegend': True,
                },
                # Base case
                {
                    'x': year_labels,
                    'y': base_values,
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': 'Base Case',
                    'line': {'color': Styles.colorPalette[0], 'width': 3},
                },
                # Market crash
                {
                    'x': year_labels,
                    'y': crash_values,
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': 'Market Crash',
                    'line': {'color': Styles.strongRed, 'width': 2, 'dash': 'dashdot'},
                },
                # FIRE number line
                {
                    'x': year_labels,
                    'y': [fire_number] * len(year_labels),
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': 'FIRE Number',
                    'line': {'color': Styles.colorPalette[3], 'dash': 'dash', 'width': 2},
                },
            ],
            'layout': Styles.graph_layout(
                title='Portfolio Projection Scenarios',
                xaxis={'title': 'Years'},
                yaxis={'title': 'Portfolio Value'},
                legend={'orientation': 'h', 'y': -0.15},
            ),
        }

        # ── Chart 2: Impact of Additional Savings (half width bar chart) ──
        savings_levels = [0, 500, 1000, 2000, 3000]
        end_values = []
        for s in savings_levels:
            contrib = (current_monthly_savings + s) * 12
            vals = _project_portfolio(portfolio, market_return, contrib, years)
            end_values.append(vals[-1])

        bar_colors = [Styles.purple_list[i % len(Styles.purple_list)] for i in range(len(savings_levels))]

        savings_chart = {
            'data': [{
                'x': [f"+{s:,}/mo" for s in savings_levels],
                'y': end_values,
                'type': 'bar',
                'marker': {'color': bar_colors},
                'text': [f"{v:,.0f}" for v in end_values],
                'textposition': 'outside',
            }],
            'layout': Styles.graph_layout(
                title='Impact of Additional Savings',
                xaxis={'title': 'Extra Monthly Savings'},
                yaxis={'title': f'Portfolio After {years} Years'},
            ),
        }

        # ── Chart 3: Inflation Impact (half width line chart) ──
        inflation_chart = {
            'data': [
                {
                    'x': year_labels,
                    'y': base_values,
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': 'Nominal',
                    'line': {'color': Styles.colorPalette[0], 'width': 3},
                },
                {
                    'x': year_labels,
                    'y': real_values,
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': 'Real (Inflation-Adjusted)',
                    'line': {'color': Styles.colorPalette[2], 'width': 3, 'dash': 'dash'},
                    'fill': 'tonexty',
                    'fillcolor': _hex_to_rgba(Styles.strongRed, 0.08),
                },
            ],
            'layout': Styles.graph_layout(
                title='Inflation Impact',
                xaxis={'title': 'Years'},
                yaxis={'title': 'Portfolio Value'},
                legend={'orientation': 'h', 'y': -0.15},
            ),
        }

        # ── Assemble charts ──
        charts = html.Div([
            html.Div([
                dcc.Graph(id='scenario-projection-chart', figure=scenario_chart)
            ], className="card", style=Styles.STYLE(100)),

            html.Div([
                dcc.Graph(id='scenario-savings-chart', figure=savings_chart)
            ], className="card", style=Styles.STYLE(48)),

            html.Div([''], style=Styles.FILLER()),

            html.Div([
                dcc.Graph(id='scenario-inflation-chart', figure=inflation_chart)
            ], className="card", style=Styles.STYLE(48)),
        ])

        return kpis, charts
