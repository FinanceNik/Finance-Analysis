"""DRIP (Dividend Reinvestment Plan) Calculator — project dividend growth over time."""
import Styles
from dash import dcc, html, Input, Output, State
from dash.exceptions import PreventUpdate


def layout():
    return html.Div([
        html.Div([
            html.H4("DRIP Calculator"),
            html.P("Project how dividend reinvestment compounds over time.",
                   className="page-subtitle"),
        ], className="page-header"),

        html.Div([
            html.Div([
                html.Label("Initial Investment ($)"),
                dcc.Input(id="drip-investment", type="number", value=10000, min=0,
                          style={"width": "160px", "padding": "8px 12px",
                                 "borderRadius": "8px", "border": "1px solid #ccc"}),
            ], style={"marginRight": "16px"}),
            html.Div([
                html.Label("Annual Dividend Yield (%)"),
                dcc.Input(id="drip-yield", type="number", value=3.0, min=0, max=100, step=0.1,
                          style={"width": "140px", "padding": "8px 12px",
                                 "borderRadius": "8px", "border": "1px solid #ccc"}),
            ], style={"marginRight": "16px"}),
            html.Div([
                html.Label("Dividend Growth Rate (%)"),
                dcc.Input(id="drip-div-growth", type="number", value=5.0,
                          min=0.1, max=99.9, step=0.1,
                          style={"width": "140px", "padding": "8px 12px",
                                 "borderRadius": "8px", "border": "1px solid #ccc"}),
            ], style={"marginRight": "16px"}),
            html.Div([
                html.Label("Price Appreciation Rate (%)"),
                dcc.Input(id="drip-price-growth", type="number", value=7.0,
                          min=0.1, max=99.9, step=0.1,
                          style={"width": "140px", "padding": "8px 12px",
                                 "borderRadius": "8px", "border": "1px solid #ccc"}),
            ], style={"marginRight": "16px"}),
            html.Div([
                html.Label("Years"),
                dcc.Input(id="drip-years", type="number", value=20, min=1, max=50,
                          style={"width": "80px", "padding": "8px 12px",
                                 "borderRadius": "8px", "border": "1px solid #ccc"}),
            ]),
        ], style={"display": "flex", "alignItems": "flex-end", "gap": "8px",
                  "padding": "10px 15px", "flexWrap": "wrap"}),

        html.Div(id="drip-feedback",
                 style={"padding": "0 15px", "fontSize": "13px", "minHeight": "20px"}),

        html.Div(id="drip-results", children=Styles.skeleton_chart()),
    ])


def register_callbacks(app):
    @app.callback(
        [Output("drip-results", "children"),
         Output("drip-feedback", "children")],
        [Input("drip-investment", "value"),
         Input("drip-yield", "value"),
         Input("drip-div-growth", "value"),
         Input("drip-price-growth", "value"),
         Input("drip-years", "value")],
    )
    def calculate_drip(investment, div_yield, div_growth, price_growth, years):
        # ── Input validation with clamping ──
        investment = investment or 10000
        if investment < 0:
            investment = 0

        div_yield = div_yield if div_yield is not None else 3.0
        div_yield = max(0, min(100, div_yield))

        # Clamp growth rates to (0, 100) exclusive
        div_growth = div_growth if div_growth is not None else 5.0
        if div_growth <= 0 or div_growth >= 100:
            div_growth = max(0.1, min(99.9, div_growth))

        price_growth = price_growth if price_growth is not None else 7.0
        if price_growth <= 0 or price_growth >= 100:
            price_growth = max(0.1, min(99.9, price_growth))

        years = years if years is not None else 20
        years = max(1, min(50, int(years)))

        feedback = ""
        # Notify user if values were clamped
        notes = []
        if div_growth == 0.1 or div_growth == 99.9:
            notes.append("Dividend growth rate clamped to valid range (0.1% - 99.9%)")
        if price_growth == 0.1 or price_growth == 99.9:
            notes.append("Price appreciation rate clamped to valid range (0.1% - 99.9%)")
        if notes:
            feedback = html.Span("; ".join(notes),
                                 style={"color": "#f5a623", "fontSize": "12px"})

        # ── Projection ──
        portfolio_value = float(investment)
        annual_dividend = portfolio_value * (div_yield / 100.0)
        total_dividends = 0.0

        yearly_data = []
        for yr in range(1, years + 1):
            # Reinvest dividends
            portfolio_value += annual_dividend
            total_dividends += annual_dividend

            # Appreciate portfolio
            portfolio_value *= (1 + price_growth / 100.0)

            # Grow the dividend
            annual_dividend = portfolio_value * (div_yield / 100.0) * ((1 + div_growth / 100.0) ** yr) / ((1 + price_growth / 100.0) ** yr)
            # Simplified: just grow yield on current value
            annual_dividend = portfolio_value * (div_yield / 100.0)

            yearly_data.append({
                "year": yr,
                "value": portfolio_value,
                "annual_div": annual_dividend,
                "total_divs": total_dividends,
            })

        final = yearly_data[-1] if yearly_data else {"value": investment, "annual_div": 0, "total_divs": 0}

        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[d["year"] for d in yearly_data],
            y=[d["value"] for d in yearly_data],
            name="Portfolio Value",
            fill="tozeroy",
            line={"color": Styles.colorPalette[1]},
        ))
        fig.add_trace(go.Scatter(
            x=[d["year"] for d in yearly_data],
            y=[d["total_divs"] for d in yearly_data],
            name="Cumulative Dividends",
            line={"color": Styles.strongGreen, "dash": "dot"},
        ))
        fig.update_layout(
            **Styles.graph_layout(title="DRIP Projection"),
            xaxis_title="Year",
            yaxis_title="Value ($)",
            hovermode="x unified",
        )

        results = html.Div([
            html.Div([
                Styles.kpiboxes("Final Value", f"${final['value']:,.0f}", Styles.colorPalette[0]),
                Styles.kpiboxes("Annual Dividend", f"${final['annual_div']:,.0f}", Styles.colorPalette[1]),
                Styles.kpiboxes("Total Dividends", f"${final['total_divs']:,.0f}", Styles.strongGreen),
                Styles.kpiboxes("Growth Multiple", f"{final['value'] / investment:.1f}x" if investment > 0 else "N/A",
                                Styles.colorPalette[2]),
            ], className="kpi-row"),
            html.Div([
                dcc.Graph(figure=fig, config={"displayModeBar": False}),
            ], className="card", style={"marginTop": "12px"}),
        ])

        return results, feedback
