from dash import dcc, html, Input, Output
from datetime import datetime, date
import dash_bootstrap_components as dbc
import Styles
import config
import dataTransformationProjections as dtp
import user_settings

def layout():
    return html.Div([
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

        html.Div(id="proj-kpis", children=Styles.skeleton_kpis(4)),
        html.Div([
            dcc.Loading(
                dcc.Graph(id='proj-monte-carlo-chart'),
                type="dot",
            )
        ], className="card"),

        # ── Financial Goals Section ──
        html.H4("Financial Goals", style={"marginTop": "40px"}),
        html.Div(id="proj-goals-cards"),
        html.Div([
            dcc.Loading(
                dcc.Graph(id='proj-goals-timeline'),
                type="dot",
            )
        ], className="card"),
    ])

def _build_goals_section(monthly_savings):
    """Build goal progress cards and a Gantt-style timeline chart."""
    today = date.today()
    goals = config.FINANCIAL_GOALS
    if not goals:
        return html.Div(), {}

    # ── Goal progress cards ──
    cards = []
    timeline_traces = []
    goal_names = []
    colors_map = {"High": Styles.colorPalette[0], "Medium": Styles.colorPalette[1],
                  "Low": Styles.colorPalette[2]}

    for i, goal in enumerate(goals):
        name = goal["name"]
        target = goal["target"]
        deadline_str = goal["deadline"]
        priority = goal.get("priority", "Medium")

        try:
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue

        months_left = max((deadline.year - today.year) * 12 + (deadline.month - today.month), 1)
        monthly_needed = target / months_left
        on_track = monthly_savings >= monthly_needed if monthly_savings > 0 else False

        # Projected completion: months to reach target at current savings rate
        if monthly_savings > 0:
            months_to_complete = target / monthly_savings
            projected_date = date(
                today.year + int((today.month + months_to_complete - 1) // 12),
                int((today.month + months_to_complete - 1) % 12) + 1,
                1,
            )
        else:
            months_to_complete = float('inf')
            projected_date = None

        # Progress as pct of time-based saving (how much you'd have saved by now)
        total_months = max((deadline.year - today.year) * 12 + (deadline.month - today.month) +
                          months_left, months_left)
        saved_so_far = monthly_savings * max(0, total_months - months_left) if monthly_savings > 0 else 0
        pct = min(saved_so_far / target * 100, 100) if target > 0 else 0

        status_badge = html.Span(
            "On Track" if on_track else "Behind",
            style={
                "color": "white",
                "backgroundColor": Styles.strongGreen if on_track else Styles.strongRed,
                "padding": "2px 10px",
                "borderRadius": "12px",
                "fontSize": "12px",
                "fontWeight": "600",
            },
        )

        card = html.Div([
            html.Div([
                html.Div([
                    html.Strong(name, style={"fontSize": "16px"}),
                    status_badge,
                ], style={"display": "flex", "justifyContent": "space-between",
                          "alignItems": "center", "marginBottom": "8px"}),
                html.Div(f"Target: {config.CURRENCY_SYMBOLS.get(config.BASE_CURRENCY, '')} "
                         f"{target:,.0f}  |  Deadline: {deadline_str}  |  Priority: {priority}",
                         style={"fontSize": "13px", "opacity": "0.7", "marginBottom": "10px"}),
                dbc.Progress(
                    value=pct,
                    color="success" if on_track else "danger",
                    className="mb-2",
                    style={"height": "8px"},
                ),
                html.Div([
                    html.Span(f"Monthly needed: {config.CURRENCY_SYMBOLS.get(config.BASE_CURRENCY, '')} "
                              f"{monthly_needed:,.0f}",
                              style={"fontSize": "13px"}),
                    html.Span(f"Remaining: {config.CURRENCY_SYMBOLS.get(config.BASE_CURRENCY, '')} "
                              f"{target - saved_so_far:,.0f}",
                              style={"fontSize": "13px", "marginLeft": "20px"}),
                ], style={"display": "flex", "flexWrap": "wrap", "gap": "4px"}),
            ], style={"padding": "16px"}),
        ], className="card", style={"marginBottom": "12px"})

        cards.append(card)

        # ── Timeline trace data ──
        goal_names.append(name)
        bar_color = colors_map.get(priority, Styles.colorPalette[1])

        # Horizontal bar from today to deadline
        timeline_traces.append({
            'type': 'bar',
            'x': [months_left],
            'y': [name],
            'orientation': 'h',
            'name': f'{name} (remaining)',
            'marker': {'color': bar_color, 'opacity': 0.5},
            'showlegend': False,
            'hovertemplate': f'{name}: {months_left} months to deadline<extra></extra>',
        })

        # Projected completion marker
        if projected_date and months_to_complete != float('inf'):
            marker_x = min(months_to_complete, months_left * 1.5)
            marker_color = Styles.strongGreen if on_track else Styles.strongRed
            timeline_traces.append({
                'type': 'scatter',
                'x': [marker_x],
                'y': [name],
                'mode': 'markers+text',
                'marker': {'symbol': 'diamond', 'size': 14, 'color': marker_color},
                'text': [f'{int(months_to_complete)}mo'],
                'textposition': 'middle right',
                'showlegend': False,
                'hovertemplate': (f'{name}: projected completion in '
                                 f'{int(months_to_complete)} months<extra></extra>'),
            })

    # ── Timeline figure ──
    timeline_figure = {
        'data': timeline_traces,
        'layout': Styles.graph_layout(
            title='Goal Timeline (months from now)',
            xaxis={'title': 'Months', 'rangemode': 'tozero'},
            yaxis={'autorange': 'reversed'},
            barmode='overlay',
            height=max(200, 80 * len(goal_names)),
            margin={'l': 150},
        ),
    }

    return html.Div(cards), timeline_figure


def register_callbacks(app):
    @app.callback(
        [Output("proj-monte-carlo-chart", "figure"),
         Output("proj-kpis", "children"),
         Output("proj-goals-cards", "children"),
         Output("proj-goals-timeline", "figure")],
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
        ], className="kpi-row")

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
        # ── Financial Goals ──
        budget = user_settings.get("budget", {}) or {}
        inc = budget.get("income", {}) or {}
        monthly_income = sum(v for v in inc.values() if isinstance(v, (int, float)))
        monthly_expenses = annual_expenses / 12 if annual_expenses > 0 else 0
        monthly_savings = max(monthly_income - monthly_expenses, 0)

        goals_cards, goals_timeline = _build_goals_section(monthly_savings)

        return figure, kpis, goals_cards, goals_timeline
