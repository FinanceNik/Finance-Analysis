from dash import dcc, html, Input, Output
import Styles
import dataLoadRealEstate as dlre

def layout():
    return html.Div([
        html.H4("Real Estate Investment Projection"),

        # --- Input controls ---
        html.Div([
            html.Div([
                html.Label("Property Value (CHF)"),
                dcc.Input(
                    id="re-starting-value", type="number",
                    value=350000, step=10000, min=50000,
                    style={"width": "100%", "padding": "6px"}
                ),
            ], style={"width": "18%", "display": "inline-block", "padding": "10px 15px"}),

            html.Div([
                html.Label("Annual Growth Rate (%)"),
                dcc.Slider(
                    id="re-growth-rate",
                    min=0, max=8, step=0.5, value=3,
                    marks={i: f"{i}%" for i in range(0, 9)},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ], style={"width": "25%", "display": "inline-block", "padding": "10px 15px"}),

            html.Div([
                html.Label("Monthly Rental Income (CHF)"),
                dcc.Input(
                    id="re-income", type="number",
                    value=1700, step=100, min=0,
                    style={"width": "100%", "padding": "6px"}
                ),
            ], style={"width": "18%", "display": "inline-block", "padding": "10px 15px"}),

            html.Div([
                html.Label("Monthly Costs (CHF)"),
                dcc.Input(
                    id="re-costs", type="number",
                    value=1200, step=100, min=0,
                    style={"width": "100%", "padding": "6px"}
                ),
            ], style={"width": "18%", "display": "inline-block", "padding": "10px 15px"}),

            html.Div([
                html.Label("Projection Years"),
                dcc.Slider(
                    id="re-years",
                    min=5, max=40, step=5, value=20,
                    marks={i: f"{i}y" for i in range(5, 41, 5)},
                    tooltip={"placement": "bottom", "always_visible": True},
                ),
            ], style={"width": "18%", "display": "inline-block", "padding": "10px 15px"}),
        ], style={"marginBottom": "10px"}),

        # --- KPI boxes (dynamic) ---
        html.Div(id="re-kpi-boxes", children=Styles.skeleton_kpis(4)),

        # --- Chart ---
        html.Div([
            dcc.Loading(
                dcc.Graph(id='re-projection-chart'),
                type="dot",
            )
        ], className="card")
    ])

def register_callbacks(app):
    @app.callback(
        [Output("re-kpi-boxes", "children"),
         Output("re-projection-chart", "figure")],
        [Input("re-starting-value", "value"),
         Input("re-growth-rate", "value"),
         Input("re-income", "value"),
         Input("re-costs", "value"),
         Input("re-years", "value")]
    )
    def update_real_estate(starting_value, growth_rate, monthly_income, monthly_costs, years):
        starting_value = starting_value or 350000
        growth_rate = (growth_rate or 3) / 100.0
        monthly_income = monthly_income or 1700
        monthly_costs = monthly_costs or 1200
        years = years or 20

        annual_income = monthly_income * 12
        annual_costs = monthly_costs * 12

        df = dlre.real_estate_projection(
            starting_value=starting_value,
            growth_rate=growth_rate,
            costs=annual_costs,
            income=annual_income,
            years=years
        )

        final_value = df['asset_value_with_appreciation'].iloc[-1]
        total_appreciation = final_value - starting_value
        total_income = annual_income * years
        total_costs = annual_costs * years
        net_profit = total_appreciation + total_income - total_costs

        kpis = html.Div([
            Styles.kpiboxes('Property Value', f"{starting_value:,.0f}", Styles.colorPalette[0]),
            Styles.kpiboxes('Annual Net Cash Flow', f"{annual_income - annual_costs:,.0f}", Styles.colorPalette[1]),
            Styles.kpiboxes(f'Value After {years}y', f"{final_value:,.0f}", Styles.colorPalette[2]),
            Styles.kpiboxes('Total Net Profit', f"{net_profit:,.0f}", Styles.colorPalette[3]),
        ], className="kpi-row")

        figure = {
            'data': [
                {
                    'x': df.index.tolist(),
                    'y': df['costs'].tolist(),
                    'type': 'bar',
                    'name': 'Cumulative Costs',
                    'width': 0.25,
                    'marker': {'color': 'red'}
                },
                {
                    'x': df.index.tolist(),
                    'y': df['income'].tolist(),
                    'type': 'bar',
                    'name': 'Cumulative Income',
                    'width': 0.25,
                    'marker': {'color': 'green'}
                },
                {
                    'x': df.index.tolist(),
                    'y': df['asset_value_with_appreciation'].tolist(),
                    'type': 'bar',
                    'name': 'Asset Value',
                    'width': 0.25,
                    'marker': {'color': Styles.colorPalette[0]}
                },
            ],
            'layout': Styles.graph_layout(
                title=f'Real Estate Projection Over {years} Years',
                xaxis={'title': 'Year'},
                yaxis={'title': 'CHF'},
            ),
        }

        return kpis, figure
