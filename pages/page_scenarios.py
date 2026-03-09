from dash import dcc, html, Input, Output
import numpy as np
import Styles
import dataLoadPositions as dlp
import user_settings

def layout():
    return html.Div([
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
        dcc.Loading(
            html.Div(id="scenario-kpis", children=Styles.skeleton_kpis(4)),
            type="dot"),
        dcc.Loading(
            html.Div(id="scenario-charts", children=Styles.skeleton_chart()),
            type="dot"),

        # --- Withdrawal Strategy Simulator ---
        html.H4("Withdrawal Strategy Simulator"),
        html.Div([
            html.Div([
                html.Label("Retirement Portfolio"),
                dcc.Input(id="withdraw-portfolio", type="number", value=1_000_000,
                          style={"width": "100%", "padding": "6px"}),
            ], style={"width": "22%", "display": "inline-block", "padding": "10px 20px"}),
            html.Div([
                html.Label("Annual Expenses"),
                dcc.Input(id="withdraw-expenses", type="number", value=60_000,
                          style={"width": "100%", "padding": "6px"}),
            ], style={"width": "22%", "display": "inline-block", "padding": "10px 20px"}),
            html.Div([
                html.Label("Expected Return (%)"),
                dcc.Slider(id="withdraw-return", min=2, max=12, step=0.5, value=6,
                           marks={i: f"{i}%" for i in range(2, 13, 2)},
                           tooltip={"placement": "bottom", "always_visible": True}),
            ], style={"width": "22%", "display": "inline-block", "padding": "10px 20px"}),
            html.Div([
                html.Label("Strategy"),
                dcc.Dropdown(id="withdraw-strategy",
                             options=[
                                 {"label": "Fixed 4% Rule", "value": "4pct"},
                                 {"label": "Variable % (Guardrails)", "value": "variable"},
                                 {"label": "Bucket Strategy", "value": "bucket"},
                             ], value="4pct", clearable=False),
            ], style={"width": "22%", "display": "inline-block", "padding": "10px 20px"}),
        ]),
        dcc.Loading(html.Div(id="withdraw-results", children=html.Div([
            Styles.skeleton_kpis(4), Styles.skeleton_chart(),
        ])), type="dot"),
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

def _simulate_4pct(portfolio, annual_expenses, return_rate, years):
    """Fixed 4% Rule: withdraw 4% of initial portfolio (or annual_expenses),
    adjust for 2% inflation each year, apply return to remaining balance."""
    values = [portfolio]
    p = portfolio
    withdrawal = annual_expenses  # could also be 0.04 * portfolio
    for yr in range(years):
        withdrawal_this_year = withdrawal * (1.02 ** yr)
        p = (p - withdrawal_this_year) * (1 + return_rate)
        values.append(round(p))
    return values

def _simulate_variable(portfolio, return_rate, years):
    """Variable % / Guardrails: base 4%, floor 3%, ceiling 5% of current value."""
    values = [portfolio]
    p = portfolio
    for _ in range(years):
        base_wd = 0.04 * p
        floor_wd = 0.03 * p
        ceil_wd = 0.05 * p
        withdrawal = max(floor_wd, min(base_wd, ceil_wd))
        p = (p - withdrawal) * (1 + return_rate)
        values.append(round(p))
    return values

def _simulate_bucket(portfolio, annual_expenses, return_rate, years):
    """Bucket strategy:
    Bucket 1 – 2 years of expenses in cash (0% return)
    Bucket 2 – 5 years of expenses in bonds (4% return)
    Bucket 3 – remainder in equities (expected_return%)
    Each year: withdraw from Bucket 1, refill from Bucket 2, refill Bucket 2 from Bucket 3.
    """
    b1 = min(annual_expenses * 2, portfolio)
    b2 = min(annual_expenses * 5, portfolio - b1)
    b3 = portfolio - b1 - b2
    values = [portfolio]
    for _ in range(years):
        # Withdraw annual expenses from Bucket 1
        withdrawal = min(annual_expenses, b1)
        b1 -= withdrawal
        # Refill Bucket 1 from Bucket 2
        refill_b1 = min(annual_expenses - b1, b2)  # top up b1 to ~1yr expenses
        b2 -= refill_b1
        b1 += refill_b1
        # Refill Bucket 2 from Bucket 3
        target_b2 = annual_expenses * 5
        refill_b2 = min(max(target_b2 - b2, 0), b3)
        b3 -= refill_b2
        b2 += refill_b2
        # Apply returns
        # Bucket 1: cash, 0% return
        b2 = b2 * 1.04           # bonds 4%
        b3 = b3 * (1 + return_rate)  # equities
        total = b1 + b2 + b3
        values.append(round(total))
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
        ], className="kpi-row")

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
            ], className="card"),

            html.Div([
                html.Div([
                    dcc.Graph(id='scenario-savings-chart', figure=savings_chart)
                ], className="card"),
                html.Div([
                    dcc.Graph(id='scenario-inflation-chart', figure=inflation_chart)
                ], className="card"),
            ], className="grid-2"),
        ])

        return kpis, charts

    # ── Withdrawal Strategy Simulator callback ──

    @app.callback(
        Output("withdraw-results", "children"),
        [Input("withdraw-portfolio", "value"),
         Input("withdraw-expenses", "value"),
         Input("withdraw-return", "value"),
         Input("withdraw-strategy", "value")]
    )
    def update_withdrawal(portfolio, expenses, expected_return, strategy):
        portfolio = portfolio or 1_000_000
        expenses = expenses or 60_000
        expected_return = expected_return or 6
        strategy = strategy or "4pct"

        return_rate = expected_return / 100
        years = 30

        # ── Deterministic simulation for the selected strategy ──
        values_4pct = _simulate_4pct(portfolio, expenses, return_rate, years)
        values_variable = _simulate_variable(portfolio, return_rate, years)
        values_bucket = _simulate_bucket(portfolio, expenses, return_rate, years)

        strategy_map = {
            "4pct": values_4pct,
            "variable": values_variable,
            "bucket": values_bucket,
        }
        selected_values = strategy_map[strategy]

        # Years until depletion for selected strategy
        depletion_year = "30+"
        for yr, val in enumerate(selected_values):
            if val <= 0:
                depletion_year = str(yr)
                break

        final_portfolio = max(selected_values[-1], 0)

        # Safe withdrawal rate: expenses / initial portfolio
        safe_wr = (expenses / portfolio * 100) if portfolio > 0 else 0

        # ── Monte Carlo survival probability (200 runs) ──
        surviving = 0
        for _ in range(200):
            p = portfolio
            alive = True
            for yr in range(years):
                actual_return = return_rate + np.random.normal(0, 0.15)
                if strategy == "4pct":
                    withdrawal = expenses * (1.02 ** yr)
                elif strategy == "variable":
                    base_wd = 0.04 * p
                    floor_wd = 0.03 * p
                    ceil_wd = 0.05 * p
                    withdrawal = max(floor_wd, min(base_wd, ceil_wd))
                else:  # bucket — simplified for MC
                    withdrawal = expenses * (1.02 ** yr)
                p = (p - withdrawal) * (1 + actual_return)
                if p <= 0:
                    alive = False
                    break
            if alive and p > 0:
                surviving += 1
        survival_pct = surviving / 200 * 100

        # ── KPI row ──
        kpis = html.Div([
            Styles.kpiboxes("Years Until Depletion", depletion_year, Styles.colorPalette[0]),
            Styles.kpiboxes("Survival Probability",
                            f"{survival_pct:.0f}%",
                            Styles.strongGreen if survival_pct >= 80 else Styles.strongRed),
            Styles.kpiboxes("Final Portfolio Value",
                            f"${final_portfolio:,.0f}",
                            Styles.colorPalette[2]),
            Styles.kpiboxes("Safe Withdrawal Rate",
                            f"{safe_wr:.1f}%",
                            Styles.purple_list[0]),
        ], className="kpi-row")

        # ── Overlay chart: all 3 strategies ──
        year_labels = list(range(years + 1))
        chart_colors = [Styles.colorPalette[0], Styles.purple_list[0], Styles.colorPalette[2]]

        withdraw_chart = {
            'data': [
                {
                    'x': year_labels,
                    'y': [max(v, 0) for v in values_4pct],
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': 'Fixed 4% Rule',
                    'line': {'color': chart_colors[0], 'width': 3},
                },
                {
                    'x': year_labels,
                    'y': [max(v, 0) for v in values_variable],
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': 'Variable % (Guardrails)',
                    'line': {'color': chart_colors[1], 'width': 3, 'dash': 'dash'},
                },
                {
                    'x': year_labels,
                    'y': [max(v, 0) for v in values_bucket],
                    'type': 'scatter',
                    'mode': 'lines',
                    'name': 'Bucket Strategy',
                    'line': {'color': chart_colors[2], 'width': 3, 'dash': 'dot'},
                },
            ],
            'layout': Styles.graph_layout(
                title='Withdrawal Strategy Comparison — Portfolio Balance Over 30 Years',
                xaxis={'title': 'Year'},
                yaxis={'title': 'Portfolio Value ($)'},
                legend={'orientation': 'h', 'y': -0.15},
            ),
        }

        chart_div = html.Div([
            html.Div([
                dcc.Graph(id='withdraw-comparison-chart', figure=withdraw_chart)
            ], className="card"),
        ])

        return html.Div([kpis, chart_div])
