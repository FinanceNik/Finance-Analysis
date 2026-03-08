import pandas as pd
import numpy as np
from dash import dcc, html
from datetime import datetime
import Styles
import dataLoadTransactions as dlt
import user_settings


def _get_budget():
    """Load budget settings with safe defaults."""
    saved = user_settings.get("budget", {}) or {}
    inc = saved.get("income", {}) or {}
    exp = saved.get("expenses", {}) or {}
    return inc, exp


def _monthly_income_fields(inc):
    """Extract monthly income components from budget."""
    salary = inc.get("salary", 0) or 0
    side = inc.get("side", 0) or 0
    dividends = inc.get("dividends", 0) or 0
    other = inc.get("other", 0) or 0
    return salary, side, dividends, other


def _monthly_expense_total(exp):
    """Sum all monthly expense categories from budget."""
    return sum(v for v in exp.values() if isinstance(v, (int, float)))


def _get_last_12_month_labels():
    """Return list of (year, month_num, label) for the last 12 months plus current month."""
    today = datetime.today()
    result = []
    for i in range(11, -1, -1):
        # Go back i months from current month
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        label = f"{dlt.months[month - 1]} {year}"
        result.append((year, month, label))
    return result


def _get_dividend_by_month():
    """Get actual dividend amounts per (year, month) from transaction data."""
    df = dlt.ingest_transactions()
    if df.empty:
        return {}

    if "transaction" not in df.columns or "date" not in df.columns:
        return {}

    dividends = df[df["transaction"].str.lower() == "dividend"].copy()
    if dividends.empty:
        return {}

    dividends["year"] = dividends["date"].dt.year
    dividends["month"] = dividends["date"].dt.month
    grouped = dividends.groupby(["year", "month"])["net_amount"].sum()
    return grouped.to_dict()


def _build_monthly_data():
    """Build last 12 months of income, expense, and net savings data.

    Returns:
        month_labels: list of str labels like 'Jan 2025'
        monthly_income: list of float (total income per month)
        monthly_expenses: list of float (total expenses per month, positive value)
        monthly_net: list of float (income - expenses)
        monthly_salary: list of float
        monthly_side: list of float
        monthly_dividends: list of float (actual from transactions)
        monthly_expense_breakdown: dict of {category: [12 values]}
    """
    inc, exp = _get_budget()
    salary, side, budget_dividends, other_inc = _monthly_income_fields(inc)
    total_budget_expenses = _monthly_expense_total(exp)

    # Budget income without dividends (those come from real data)
    budget_income_ex_div = salary + side + other_inc

    months_info = _get_last_12_month_labels()
    div_by_month = _get_dividend_by_month()

    month_labels = []
    monthly_income = []
    monthly_expenses = []
    monthly_net = []
    monthly_salary_list = []
    monthly_side_list = []
    monthly_dividends_list = []

    for year, month, label in months_info:
        actual_div = div_by_month.get((year, month), budget_dividends)
        total_income = budget_income_ex_div + actual_div
        total_exp = total_budget_expenses

        month_labels.append(label)
        monthly_income.append(round(total_income, 2))
        monthly_expenses.append(round(total_exp, 2))
        monthly_net.append(round(total_income - total_exp, 2))
        monthly_salary_list.append(salary)
        monthly_side_list.append(side)
        monthly_dividends_list.append(round(actual_div, 2))

    # Expense breakdown by category (constant from budget)
    expense_categories = {
        "Rent": exp.get("rent", 0) or 0,
        "Utilities": exp.get("utilities", 0) or 0,
        "Insurance": exp.get("insurance", 0) or 0,
        "Food": exp.get("food", 0) or 0,
        "Transport": exp.get("transport", 0) or 0,
        "Entertainment": exp.get("entertainment", 0) or 0,
        "Taxes": exp.get("taxes", 0) or 0,
        "Other": exp.get("other", 0) or 0,
    }
    monthly_expense_breakdown = {
        cat: [val] * 12 for cat, val in expense_categories.items() if val > 0
    }

    return (
        month_labels, monthly_income, monthly_expenses, monthly_net,
        monthly_salary_list, monthly_side_list, monthly_dividends_list,
        monthly_expense_breakdown,
    )


def _build_waterfall_chart(month_labels, monthly_net):
    """Build a waterfall chart showing monthly net savings with an annual total."""
    labels = month_labels + ["Total"]
    values = monthly_net + [sum(monthly_net)]
    measures = ["relative"] * len(monthly_net) + ["total"]

    chart = {
        "data": [{
            "type": "waterfall",
            "orientation": "v",
            "x": labels,
            "y": values,
            "measure": measures,
            "connector": {"line": {"color": "rgba(0,0,0,0)"}},
            "increasing": {"marker": {"color": Styles.strongGreen}},
            "decreasing": {"marker": {"color": Styles.strongRed}},
            "totals": {"marker": {"color": Styles.colorPalette[0]}},
            "textposition": "outside",
            "text": [f"{v:,.0f}" for v in values],
        }],
        "layout": Styles.graph_layout(
            title="Monthly Cash Flow Waterfall",
            xaxis={"tickangle": -45},
            yaxis={"title": "Net Savings"},
            margin={"t": 50, "b": 80, "l": 60, "r": 30},
        ),
    }
    return chart


def _build_income_breakdown_chart(month_labels, monthly_salary, monthly_side, monthly_dividends):
    """Build a stacked bar chart of income sources over last 12 months."""
    traces = []

    if any(v > 0 for v in monthly_salary):
        traces.append({
            "type": "bar",
            "x": month_labels,
            "y": monthly_salary,
            "name": "Salary",
            "marker": {"color": Styles.colorPalette[0]},
        })

    if any(v > 0 for v in monthly_side):
        traces.append({
            "type": "bar",
            "x": month_labels,
            "y": monthly_side,
            "name": "Side Income",
            "marker": {"color": Styles.colorPalette[1]},
        })

    if any(v > 0 for v in monthly_dividends):
        traces.append({
            "type": "bar",
            "x": month_labels,
            "y": monthly_dividends,
            "name": "Dividends",
            "marker": {"color": Styles.strongGreen},
        })

    if not traces:
        traces.append({
            "type": "bar",
            "x": month_labels,
            "y": [0] * len(month_labels),
            "name": "No Data",
        })

    chart = {
        "data": traces,
        "layout": Styles.graph_layout(
            title="Income Breakdown",
            barmode="stack",
            xaxis={"tickangle": -45},
            yaxis={"title": "Amount"},
            legend={"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            margin={"t": 40, "b": 80, "l": 60, "r": 20},
        ),
    }
    return chart


def _build_expense_breakdown_chart(month_labels, monthly_expense_breakdown):
    """Build a stacked bar chart of expenses by category over last 12 months."""
    colors = Styles.purple_list
    traces = []

    for i, (cat, values) in enumerate(monthly_expense_breakdown.items()):
        traces.append({
            "type": "bar",
            "x": month_labels,
            "y": values,
            "name": cat,
            "marker": {"color": colors[i % len(colors)]},
        })

    if not traces:
        traces.append({
            "type": "bar",
            "x": month_labels,
            "y": [0] * len(month_labels),
            "name": "No Data",
        })

    chart = {
        "data": traces,
        "layout": Styles.graph_layout(
            title="Expense Breakdown",
            barmode="stack",
            xaxis={"tickangle": -45},
            yaxis={"title": "Amount"},
            legend={"orientation": "h", "y": -0.2, "x": 0.5, "xanchor": "center"},
            margin={"t": 40, "b": 80, "l": 60, "r": 20},
        ),
    }
    return chart


def _build_savings_rate_chart(month_labels, monthly_income, monthly_expenses):
    """Build a line chart with filled area showing savings rate % per month."""
    savings_rates = []
    for inc_val, exp_val in zip(monthly_income, monthly_expenses):
        if inc_val > 0:
            rate = (inc_val - exp_val) / inc_val * 100
        else:
            rate = 0
        savings_rates.append(round(rate, 1))

    chart = {
        "data": [{
            "type": "scatter",
            "x": month_labels,
            "y": savings_rates,
            "mode": "lines+markers",
            "fill": "tozeroy",
            "fillcolor": "rgba(52, 199, 89, 0.2)",
            "line": {"color": Styles.strongGreen, "width": 2.5},
            "marker": {"size": 6},
            "name": "Savings Rate",
            "hovertemplate": "%{x}<br>Savings Rate: %{y:.1f}%<extra></extra>",
        }],
        "layout": Styles.graph_layout(
            title="Savings Rate Trend",
            xaxis={"tickangle": -45},
            yaxis={"title": "Savings Rate (%)", "ticksuffix": "%"},
            margin={"t": 40, "b": 80, "l": 60, "r": 30},
            hovermode="x unified",
        ),
    }
    return chart


def layout():
    inc, exp = _get_budget()
    salary, side, budget_dividends, other_inc = _monthly_income_fields(inc)
    total_budget_expenses = _monthly_expense_total(exp)

    # --- KPI calculations ---
    annual_gross_income = (salary + side + other_inc) * 12

    # Annual dividend income: prefer actual transaction data for current year
    actual_annual_dividends = dlt.total_transaction_amount(dlt.currentYear, "Dividend")
    if actual_annual_dividends and actual_annual_dividends > 0:
        annual_dividend_income = actual_annual_dividends
    else:
        annual_dividend_income = budget_dividends * 12

    annual_expenses = total_budget_expenses * 12
    annual_net_savings = annual_gross_income + annual_dividend_income - annual_expenses

    # Color coding
    net_color = Styles.strongGreen if annual_net_savings >= 0 else Styles.strongRed

    # --- Build monthly data ---
    (
        month_labels, monthly_income, monthly_expenses, monthly_net,
        monthly_salary, monthly_side, monthly_dividends,
        monthly_expense_breakdown,
    ) = _build_monthly_data()

    # --- Charts ---
    waterfall = _build_waterfall_chart(month_labels, monthly_net)
    income_breakdown = _build_income_breakdown_chart(
        month_labels, monthly_salary, monthly_side, monthly_dividends
    )
    expense_breakdown = _build_expense_breakdown_chart(
        month_labels, monthly_expense_breakdown
    )
    savings_rate = _build_savings_rate_chart(
        month_labels, monthly_income, monthly_expenses
    )

    return html.Div([
        html.Hr(),
        html.H4("Income Statement"),

        # ── Section 1: KPI Row ──
        html.Div([
            Styles.kpiboxes("Annual Gross Income", f"{annual_gross_income:,.0f}", Styles.colorPalette[0]),
            Styles.kpiboxes("Annual Dividend Income", f"{annual_dividend_income:,.0f}", Styles.strongGreen),
            Styles.kpiboxes("Annual Expenses", f"{annual_expenses:,.0f}", Styles.colorPalette[2]),
            Styles.kpiboxes("Annual Net Savings", f"{annual_net_savings:,.0f}", net_color),
        ]),
        html.Hr(),

        # ── Section 2: Waterfall Chart (full width) ──
        html.Div([
            dcc.Graph(
                id="income-waterfall",
                figure=waterfall,
                config={"displayModeBar": False},
            ),
        ], className="card", style=Styles.STYLE(100)),
        html.Hr(),

        # ── Section 3: Income & Expense Breakdown (side by side) ──
        html.Div([
            dcc.Graph(
                id="income-breakdown-chart",
                figure=income_breakdown,
                config={"displayModeBar": False},
            ),
        ], className="card", style=Styles.STYLE(48)),
        html.Div([""], style=Styles.FILLER()),
        html.Div([
            dcc.Graph(
                id="expense-breakdown-chart",
                figure=expense_breakdown,
                config={"displayModeBar": False},
            ),
        ], className="card", style=Styles.STYLE(48)),
        html.Hr(),

        # ── Section 4: Savings Rate Trend (full width) ──
        html.Div([
            dcc.Graph(
                id="savings-rate-chart",
                figure=savings_rate,
                config={"displayModeBar": False},
            ),
        ], className="card", style=Styles.STYLE(100)),
    ])
