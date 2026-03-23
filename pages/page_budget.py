import math
from dash import dcc, html, Input, Output
import Styles
import config
import dataLoadPositions as dlp
import dataLoadTransactions as dlt
import user_settings


def _hex_to_rgba(hex_color, alpha):
    """Convert hex color to rgba string."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _calc_years_to_fire(portfolio, annual_savings, fire_number, growth_rate=config.FIRE_GROWTH_RATE):
    """Calculate years to reach FIRE number with contributions and compound growth."""
    if fire_number <= 0 or portfolio >= fire_number:
        return 0
    if annual_savings <= 0 and portfolio <= 0:
        return float('inf')
    if growth_rate <= 0:
        return (fire_number - portfolio) / annual_savings if annual_savings > 0 else float('inf')
    current = portfolio
    for year in range(1, config.MAX_FIRE_YEARS):
        current = current * (1 + growth_rate) + annual_savings
        if current >= fire_number:
            return year
    return float('inf')


def layout():
    return html.Div([
        html.H4("Budget & Cash Flow"),
        html.P([
            "Budget inputs are configured on the ",
            dcc.Link("Settings page", href="/settings"),
            ".",
        ], style={"color": "var(--text-secondary)", "marginBottom": "16px"}),

        # Trigger: hidden div fires callback on page load
        html.Div(id="budget-trigger", style={"display": "none"}),
        dcc.Interval(id="budget-load-interval", interval=500, max_intervals=1),

        dcc.Loading(
            html.Div(id="budget-kpis", children=Styles.skeleton_kpis(4)),
            type="dot"),
        dcc.Loading(
            html.Div(id="budget-charts", children=Styles.skeleton_chart()),
            type="dot"),
    ])


def register_callbacks(app):
    @app.callback(
        [Output("budget-kpis", "children"),
         Output("budget-charts", "children")],
        [Input("budget-load-interval", "n_intervals")]
    )
    def update_budget(n_intervals):
        saved = user_settings.get("budget", {})
        inc = saved.get("income", {})
        exp = saved.get("expenses", {})

        salary = inc.get("salary", 9583)
        side = inc.get("side", 375)
        dividends = inc.get("dividends", 292)
        other_inc = inc.get("other", 0)

        rent = exp.get("rent", 1680)
        utilities = exp.get("utilities", 25)
        insurance = exp.get("insurance", 320)
        gebaeude = exp.get("gebaeude", 0)
        hausneben = exp.get("hausneben", 0)
        serafe = exp.get("serafe", 0)
        phone = exp.get("phone", 0)
        claude = exp.get("claude", 0)
        spotify = exp.get("spotify", 0)
        food = exp.get("food", 0)
        transport = exp.get("transport", 0)
        entertainment = exp.get("entertainment", 0)
        leibrente = exp.get("leibrente", 1200)
        taxes = exp.get("taxes", 0)
        other_exp = exp.get("other", 0)

        incomes = {"Salary": salary, "Side Income": side, "Dividends": dividends, "Other Income": other_inc}
        expenses = {"Rent": rent, "Utilities": utilities, "Health Insurance": insurance,
                    "Gebäudeversicherung": gebaeude, "Hausnebenkosten": hausneben, "SERAFE": serafe,
                    "Phone": phone, "Claude": claude, "Spotify": spotify,
                    "Food & Groceries": food, "Transport": transport, "Entertainment": entertainment,
                    "Leibrente": leibrente, "Taxes": taxes, "Other": other_exp}

        total_income = sum(incomes.values())
        total_expenses = sum(expenses.values())
        monthly_savings = total_income - total_expenses
        savings_rate = (monthly_savings / total_income * 100) if total_income > 0 else 0

        annual_expenses = total_expenses * 12
        fire_number = annual_expenses / config.FIRE_WITHDRAWAL_RATE if annual_expenses > 0 else 0
        portfolio = dlp.portfolio_total_value()
        fire_progress = (portfolio / fire_number * 100) if fire_number > 0 else 0
        annual_savings = monthly_savings * 12
        years_to_fire = _calc_years_to_fire(portfolio, annual_savings, fire_number)

        # Passive income coverage
        passive_monthly = dividends
        passive_coverage = (passive_monthly / total_expenses * 100) if total_expenses > 0 else 0

        # --- KPIs ---
        kpis = html.Div([
            Styles.kpiboxes("Monthly Income", f"{total_income:,.0f}", Styles.colorPalette[0]),
            Styles.kpiboxes("Monthly Expenses", f"{total_expenses:,.0f}", Styles.colorPalette[1]),
            Styles.kpiboxes("Monthly Savings", f"{monthly_savings:,.0f}",
                            Styles.strongGreen if monthly_savings >= 0 else Styles.strongRed),
            Styles.kpiboxes("Savings Rate", f"{savings_rate:.1f}%", Styles.colorPalette[2]),
        ], className="kpi-row")

        # --- Sankey chart ---
        sankey = _build_sankey(incomes, expenses, monthly_savings)

        # --- Expense pie ---
        pie_data = {k: v for k, v in expenses.items() if v > 0}
        if monthly_savings > 0:
            pie_data["Savings & Investment"] = monthly_savings

        pie_colors = list(Styles.purple_list[:len(pie_data)])
        if monthly_savings > 0:
            pie_colors[-1] = Styles.strongGreen

        pie_chart = {
            'data': [{
                'type': 'pie',
                'labels': list(pie_data.keys()),
                'values': list(pie_data.values()),
                'textinfo': 'label+percent',
                'hoverinfo': 'label+value+percent',
                'marker': {'colors': pie_colors},
                'hole': 0.35,
            }],
            'layout': Styles.graph_layout(title='Monthly Budget Allocation')
        }

        # --- Passive income bar ---
        passive_chart = {
            'data': [{
                'type': 'bar',
                'x': ['Dividend Income', 'Monthly Expenses'],
                'y': [passive_monthly, total_expenses],
                'marker': {'color': [Styles.strongGreen, Styles.colorPalette[1]]},
                'text': [f"{passive_monthly:,.0f}", f"{total_expenses:,.0f}"],
                'textposition': 'outside',
            }],
            'layout': Styles.graph_layout(
                title=f'Passive Income Coverage: {passive_coverage:.1f}%',
                yaxis={'title': 'CHF / month'},
            )
        }

        # --- FIRE section ---
        fire_kpis = html.Div([
            Styles.kpiboxes("FIRE Number (4% Rule)", f"{fire_number:,.0f}", Styles.colorPalette[0]),
            Styles.kpiboxes("Portfolio Value", f"{portfolio:,.0f}", Styles.colorPalette[1]),
            Styles.kpiboxes("FIRE Progress", f"{fire_progress:.1f}%",
                            Styles.strongGreen if fire_progress >= 100 else Styles.colorPalette[2]),
            Styles.kpiboxes("Years to FIRE",
                            f"{years_to_fire:.1f}" if years_to_fire < config.MAX_FIRE_YEARS else "N/A",
                            Styles.colorPalette[3]),
        ], className="kpi-row")

        progress_pct = min(fire_progress, 100)
        fire_bar = html.Div([
            html.Div(
                style={"width": f"{progress_pct}%", "height": "12px",
                       "backgroundColor": Styles.strongGreen, "borderRadius": "6px",
                       "transition": "width 0.5s ease"}
            )
        ], style={"width": "100%", "height": "12px", "backgroundColor": "var(--progress-bg)",
                  "borderRadius": "6px", "marginTop": "10px", "marginBottom": "20px"})

        # --- FIRE projection chart ---
        projection = _build_fire_projection(portfolio, annual_savings, fire_number)

        # --- Tax Estimation ---
        # TTM dividends from transaction data
        ttm_dividends = abs(dlt.total_transaction_amount(dlt.currentYear, "Dividend") or 0)
        # If current year has little data, supplement with budget estimate
        if ttm_dividends <= 0:
            ttm_dividends = dividends * 12

        est_dividend_tax = ttm_dividends * config.TAX_RATE_DIVIDENDS
        est_wealth_tax = portfolio * config.TAX_RATE_WEALTH
        annual_income = total_income * 12
        est_income_tax = annual_income * config.TAX_RATE_INCOME
        est_total_tax = est_dividend_tax + est_wealth_tax + est_income_tax

        tax_color = "#636366"  # muted grey
        tax_section = html.Div([
            html.H4("Tax Estimation"),
            html.Div([
                Styles.kpiboxes("Dividend Tax (35%)", f"{est_dividend_tax:,.0f}", tax_color),
                Styles.kpiboxes("Wealth Tax (~0.3%)", f"{est_wealth_tax:,.0f}", tax_color),
                Styles.kpiboxes("Income Tax (~25%)", f"{est_income_tax:,.0f}", tax_color),
                Styles.kpiboxes("Total Est. Annual Tax", f"{est_total_tax:,.0f}", Styles.colorPalette[2]),
            ], className="kpi-row"),
            html.P(
                "These are rough estimates. Consult a tax advisor for precise calculations.",
                style={"color": "var(--text-secondary)", "fontSize": "13px",
                       "marginTop": "8px", "fontStyle": "italic"},
            ),
        ])

        charts = html.Div([
            html.Div([
                dcc.Graph(id='budget-sankey', figure=sankey)
            ], className="card"),
            tax_section,
            html.Div([
                html.Div([
                    dcc.Graph(id='budget-pie', figure=pie_chart)
                ], className="card"),
                html.Div([
                    dcc.Graph(id='budget-passive', figure=passive_chart)
                ], className="card"),
            ], className="grid-2"),
            html.H4("Financial Independence"),
            fire_kpis,
            fire_bar,
            html.Div([
                dcc.Graph(id='budget-fire-projection', figure=projection)
            ], className="card"),
        ])

        return kpis, charts


def _build_sankey(incomes, expenses, savings):
    """Build a Sankey diagram showing cash flow from income to expenses and savings."""
    active_inc = {k: v for k, v in incomes.items() if v > 0}
    active_exp = {k: v for k, v in expenses.items() if v > 0}

    if not active_inc:
        return {'data': [], 'layout': Styles.graph_layout(title='Enter income data')}

    inc_labels = list(active_inc.keys())
    exp_labels = list(active_exp.keys())
    has_savings = savings > 0
    has_deficit = savings < 0

    if has_savings:
        exp_labels.append("Savings & Investment")
    elif has_deficit:
        exp_labels.append("Deficit")

    all_labels = inc_labels + exp_labels
    n_inc = len(inc_labels)
    n_exp = len(exp_labels)

    # Node colors
    inc_colors = ['#34c759', '#0a84ff', '#ff9f0a', '#bf5af2'][:n_inc]
    exp_colors = []
    exp_base = ['#ff3b30', '#ff6961', '#ff9500', '#ffcc00', '#5ac8fa', '#af52de', '#8e8e93', '#636366']
    for i in range(len(active_exp)):
        exp_colors.append(exp_base[i % len(exp_base)])
    if has_savings:
        exp_colors.append('#34c759')
    elif has_deficit:
        exp_colors.append('#ff3b30')

    node_colors = inc_colors + exp_colors

    # Build links: distribute each income source proportionally across expenses
    total_income = sum(active_inc.values())

    sources, targets, values, link_colors = [], [], [], []

    for i, (_, inc_val) in enumerate(active_inc.items()):
        share = inc_val / total_income if total_income > 0 else 0
        link_rgba = _hex_to_rgba(inc_colors[i], 0.25)

        for j, (_, exp_val) in enumerate(active_exp.items()):
            flow = exp_val * share
            if flow > 0:
                sources.append(i)
                targets.append(n_inc + j)
                values.append(round(flow, 2))
                link_colors.append(link_rgba)

        if has_savings:
            flow = savings * share
            if flow > 0:
                sources.append(i)
                targets.append(n_inc + len(active_exp))
                values.append(round(flow, 2))
                link_colors.append(_hex_to_rgba('#34c759', 0.25))

    return {
        'data': [{
            'type': 'sankey',
            'orientation': 'h',
            'node': {
                'pad': 20,
                'thickness': 25,
                'label': all_labels,
                'color': node_colors,
            },
            'link': {
                'source': sources,
                'target': targets,
                'value': values,
                'color': link_colors,
            }
        }],
        'layout': Styles.graph_layout(
            title='Monthly Cash Flow',
            height=450,
        )
    }


def _build_fire_projection(portfolio, annual_savings, fire_number, growth_rate=config.FIRE_GROWTH_RATE):
    """Build a projection chart showing portfolio growth toward FIRE number."""
    years = list(range(0, 31))
    values = []
    current = portfolio
    for y in years:
        values.append(round(current))
        current = current * (1 + growth_rate) + annual_savings

    return {
        'data': [
            {
                'x': years,
                'y': values,
                'type': 'scatter',
                'mode': 'lines',
                'fill': 'tozeroy',
                'name': 'Projected Portfolio',
                'line': {'color': Styles.colorPalette[0]},
            },
            {
                'x': years,
                'y': [fire_number] * len(years),
                'type': 'scatter',
                'mode': 'lines',
                'name': 'FIRE Number',
                'line': {'color': Styles.strongRed, 'dash': 'dash', 'width': 2},
            },
        ],
        'layout': Styles.graph_layout(
            title='Portfolio Projection vs FIRE Number (7% Real Return)',
            xaxis={'title': 'Years from Now'},
            yaxis={'title': 'Portfolio Value'},
        )
    }
