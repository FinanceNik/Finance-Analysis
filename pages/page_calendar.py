import pandas as pd
from datetime import datetime
from dash import dcc, html, Input, Output
import Styles
import dataLoadTransactions as dlt


# ─────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────

def _get_dividends() -> pd.DataFrame:
    """Return a DataFrame of dividend transactions with positive amounts."""
    txn = dlt.ingest_transactions()
    if txn.empty or "transaction" not in txn.columns:
        return pd.DataFrame()

    dividends = txn[txn["transaction"].str.lower() == "dividend"].copy()
    if dividends.empty:
        return pd.DataFrame()

    if "net_amount" in dividends.columns:
        dividends["amount"] = dividends["net_amount"].abs()

    return dividends


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _detect_frequency(payment_months: set) -> str:
    """Infer payment frequency from the set of months a symbol has paid."""
    n = len(payment_months)
    if n >= 10:
        return "Monthly"
    if n >= 3:
        return "Quarterly"
    if n == 2:
        return "Semi-Annual"
    if n == 1:
        return "Annual"
    return "Irregular"


def _build_calendar_data(dividends: pd.DataFrame, year: int):
    """Build per-month, per-symbol expected income based on historical patterns.

    Returns:
        month_totals: dict month_num -> total expected amount
        month_details: dict month_num -> list of {symbol, amount, frequency}
    """
    df = dividends.copy()
    df["month"] = df["date"].dt.month
    df["year"] = df["date"].dt.year

    # Which months each symbol historically pays
    symbol_months = df.groupby("symbol")["month"].apply(set).to_dict()

    # Average amount per symbol per month (across all years)
    symbol_month_avg = (
        df.groupby(["symbol", "month"])["amount"]
        .mean()
        .reset_index()
    )

    month_totals = {m: 0.0 for m in range(1, 13)}
    month_details = {m: [] for m in range(1, 13)}

    for symbol, hist_months in symbol_months.items():
        freq = _detect_frequency(hist_months)
        for m in sorted(hist_months):
            avg_row = symbol_month_avg[
                (symbol_month_avg["symbol"] == symbol)
                & (symbol_month_avg["month"] == m)
            ]
            est = avg_row["amount"].values[0] if len(avg_row) > 0 else 0
            month_totals[m] += est
            month_details[m].append({
                "symbol": symbol,
                "amount": round(est, 2),
                "frequency": freq,
            })

    # Sort each month's holdings by amount descending
    for m in month_details:
        month_details[m].sort(key=lambda x: x["amount"], reverse=True)

    return month_totals, month_details


# ─────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────

def _build_kpis(month_totals, dividends):
    """KPIs: Monthly Avg, Next Month Expected, Annual Projected, # Dividend Payers."""
    today = datetime.today()
    next_month = today.month % 12 + 1

    monthly_avg = sum(month_totals.values()) / 12
    next_month_expected = month_totals.get(next_month, 0)
    annual_projected = sum(month_totals.values())
    num_payers = dividends["symbol"].nunique() if not dividends.empty else 0

    return html.Div([
        Styles.kpiboxes("Monthly Avg Income", f"{monthly_avg:,.0f}",
                        Styles.colorPalette[0]),
        Styles.kpiboxes("Next Month Expected", f"{next_month_expected:,.0f}",
                        Styles.colorPalette[1]),
        Styles.kpiboxes("Annual Projected", f"{annual_projected:,.0f}",
                        Styles.colorPalette[2]),
        Styles.kpiboxes("Dividend Payers", f"{num_payers}",
                        Styles.colorPalette[3]),
    ], className="kpi-row")


def _build_heatmap(month_totals, year):
    """12-month calendar heatmap showing expected dividend income per month."""
    values = [round(month_totals.get(m, 0), 2) for m in range(1, 13)]

    # Reshape into a 3-row x 4-col grid (Q1-Q4)
    z = [
        values[0:4],    # Jan-Apr
        values[4:8],    # May-Aug
        values[8:12],   # Sep-Dec
    ]
    x_labels = [MONTH_NAMES[i:i + 4] for i in range(0, 12, 4)]
    x_flat = MONTH_NAMES[0:4]  # column headers: Jan Feb Mar Apr pattern
    y_labels = ["Q1-Q2a", "Q2b-Q3", "Q3b-Q4"]

    # Better: use a single row of 12 months (weeks-style) or 4x3 grid
    # Use 4 columns (quarters) x 3 rows
    z_grid = [
        [values[0], values[1], values[2]],      # Q1: Jan Feb Mar
        [values[3], values[4], values[5]],      # Q2: Apr May Jun
        [values[6], values[7], values[8]],      # Q3: Jul Aug Sep
        [values[9], values[10], values[11]],    # Q4: Oct Nov Dec
    ]
    x_months = ["Month 1", "Month 2", "Month 3"]
    y_quarters = ["Q4", "Q3", "Q2", "Q1"]

    # Simpler: 1 row x 12 columns
    chart = {
        'data': [{
            'type': 'heatmap',
            'z': [values],
            'x': MONTH_NAMES,
            'y': [str(year)],
            'text': [[f"{v:,.0f}" if v > 0 else "" for v in values]],
            'texttemplate': '%{text}',
            'hovertemplate': '%{x}: %{z:,.0f}<extra></extra>',
            'colorscale': [
                [0, 'rgba(0,0,0,0)'],
                [0.01, 'rgba(52,199,89,0.15)'],
                [0.25, 'rgba(52,199,89,0.35)'],
                [0.5, 'rgba(52,199,89,0.55)'],
                [0.75, 'rgba(52,199,89,0.75)'],
                [1, '#34c759'],
            ],
            'showscale': True,
            'colorbar': {
                'title': 'Income',
                'thickness': 12,
                'len': 0.8,
            },
        }],
        'layout': Styles.graph_layout(
            title=f'Expected Dividend Income by Month \u2014 {year}',
            xaxis={'side': 'top', 'tickangle': 0},
            yaxis={'visible': False},
            margin={'l': 20, 'r': 80, 't': 60, 'b': 20},
            height=160,
        )
    }

    return html.Div([
        dcc.Graph(id='cal-heatmap', figure=chart)
    ], className="card")


def _build_github_heatmap(dividends, year):
    """GitHub-style contribution heatmap: 12 months grid with weekly buckets."""
    df = dividends.copy()
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df["week"] = df["date"].dt.isocalendar().week.astype(int)

    # Pivot: months as columns, weeks as rows
    pivot = df.pivot_table(
        values="amount", index="week", columns="month",
        aggfunc="sum", fill_value=0,
    )

    # Fill missing weeks (1-53) and months (1-12)
    for m in range(1, 13):
        if m not in pivot.columns:
            pivot[m] = 0
    pivot = pivot.reindex(range(1, 54), fill_value=0)
    pivot = pivot[sorted(pivot.columns)]

    # For a cleaner view, aggregate to monthly totals
    monthly = df[df["year"] == year].groupby("month")["amount"].sum()
    all_monthly = [round(monthly.get(m, 0), 2) for m in range(1, 13)]

    # Build a 3x4 grid (rows = month-in-quarter, cols = quarter)
    z = [
        [all_monthly[0], all_monthly[3], all_monthly[6], all_monthly[9]],
        [all_monthly[1], all_monthly[4], all_monthly[7], all_monthly[10]],
        [all_monthly[2], all_monthly[5], all_monthly[8], all_monthly[11]],
    ]
    text = [[f"{v:,.0f}" if v > 0 else "" for v in row] for row in z]

    chart = {
        'data': [{
            'type': 'heatmap',
            'z': z,
            'x': ['Q1', 'Q2', 'Q3', 'Q4'],
            'y': ['Month 1', 'Month 2', 'Month 3'],
            'text': text,
            'texttemplate': '%{text}',
            'hovertemplate': '%{y} of %{x}: %{z:,.0f}<extra></extra>',
            'colorscale': [
                [0, 'rgba(0,0,0,0)'],
                [0.01, 'rgba(52,199,89,0.12)'],
                [0.25, 'rgba(52,199,89,0.3)'],
                [0.5, 'rgba(52,199,89,0.5)'],
                [0.75, 'rgba(52,199,89,0.7)'],
                [1, '#34c759'],
            ],
            'showscale': False,
        }],
        'layout': Styles.graph_layout(
            title=f'Actual Dividend Payments \u2014 {year}',
            yaxis={'autorange': 'reversed'},
            margin={'l': 70, 'r': 20, 't': 40, 'b': 30},
            height=220,
        )
    }

    return html.Div([
        dcc.Graph(id='cal-github-heatmap', figure=chart)
    ], className="card")


def _build_monthly_cards(month_details):
    """For each month, show which holdings pay dividends and how much."""
    cards = []
    for m in range(1, 13):
        holdings = month_details.get(m, [])
        if not holdings:
            card_body = html.P(
                "No expected payments",
                style={"fontStyle": "italic", "color": "var(--text-muted, #888)",
                       "fontSize": "12px", "margin": "4px 0"},
            )
        else:
            total = sum(h["amount"] for h in holdings)
            rows = []
            for h in holdings:
                rows.append(html.Div([
                    html.Span(h["symbol"],
                              style={"fontWeight": "600", "fontSize": "13px"}),
                    html.Span(f"{h['amount']:,.2f}",
                              style={"color": Styles.strongGreen,
                                     "fontWeight": "600", "fontSize": "13px"}),
                ], style={"display": "flex", "justifyContent": "space-between",
                          "padding": "2px 0"}))
            card_body = html.Div([
                html.Div(rows),
                html.Hr(style={"margin": "6px 0", "opacity": "0.2"}),
                html.Div([
                    html.Span("Total", style={"fontWeight": "700", "fontSize": "13px"}),
                    html.Span(f"{total:,.2f}",
                              style={"fontWeight": "700", "fontSize": "13px",
                                     "color": Styles.strongGreen}),
                ], style={"display": "flex", "justifyContent": "space-between"}),
            ])

        month_total = sum(h["amount"] for h in holdings) if holdings else 0
        cards.append(html.Div([
            html.Div([
                html.Span(MONTH_NAMES[m - 1],
                          style={"fontWeight": "700", "fontSize": "14px"}),
                html.Span(f"{month_total:,.0f}" if month_total > 0 else "",
                          style={"fontSize": "12px", "color": "var(--text-muted, #888)"}),
            ], style={"display": "flex", "justifyContent": "space-between",
                      "marginBottom": "6px",
                      "borderBottom": "2px solid var(--border-color, #ddd)",
                      "paddingBottom": "4px"}),
            card_body,
        ], className="card",
           style={"padding": "12px", "minWidth": "180px"}))

    return html.Div(cards, style={
        "display": "grid",
        "gridTemplateColumns": "repeat(auto-fill, minmax(200px, 1fr))",
        "gap": "12px",
    })


def _build_upcoming_table(month_details):
    """Next 3 months of expected payments as a table."""
    today = datetime.today()
    current_month = today.month

    upcoming = []
    for offset in range(1, 4):
        m = (current_month - 1 + offset) % 12 + 1
        holdings = month_details.get(m, [])
        for h in holdings:
            upcoming.append({
                "month": MONTH_NAMES[m - 1],
                "symbol": h["symbol"],
                "amount": h["amount"],
                "frequency": h["frequency"],
            })

    if not upcoming:
        return html.Div([
            html.P("No upcoming dividends predicted for the next 3 months.",
                   style={"fontStyle": "italic", "color": "var(--text-muted, #888)",
                          "padding": "12px 0"}),
        ])

    rows = []
    for item in upcoming:
        rows.append(html.Tr([
            html.Td(item["month"], style={"padding": "6px 10px"}),
            html.Td(item["symbol"], style={"padding": "6px 10px", "fontWeight": "600"}),
            html.Td(f"{item['amount']:,.2f}",
                     style={"padding": "6px 10px", "textAlign": "right",
                            "color": Styles.strongGreen, "fontWeight": "600"}),
            html.Td(item["frequency"],
                     style={"padding": "6px 10px", "textAlign": "center",
                            "fontSize": "12px"}),
        ]))

    return html.Div([
        html.Table([
            html.Thead(html.Tr([
                html.Th("Month", style={"padding": "8px 10px", "textAlign": "left",
                                         "borderBottom": "2px solid var(--border-color, #ddd)"}),
                html.Th("Symbol", style={"padding": "8px 10px", "textAlign": "left",
                                          "borderBottom": "2px solid var(--border-color, #ddd)"}),
                html.Th("Expected Amount", style={"padding": "8px 10px", "textAlign": "right",
                                                    "borderBottom": "2px solid var(--border-color, #ddd)"}),
                html.Th("Frequency", style={"padding": "8px 10px", "textAlign": "center",
                                              "borderBottom": "2px solid var(--border-color, #ddd)"}),
            ])),
            html.Tbody(rows),
        ], style={"width": "100%", "borderCollapse": "collapse", "fontSize": "14px"}),
    ], className="card")


# ─────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────

def _available_years(dividends):
    """Return sorted list of years present in dividend data."""
    if dividends.empty:
        return [dlt.currentYear]
    years = sorted(dividends["date"].dt.year.unique().tolist())
    if dlt.currentYear not in years:
        years.append(dlt.currentYear)
    return years


def layout():
    dividends = _get_dividends()

    if dividends.empty:
        return html.Div([
            html.H4("Income Calendar"),
            html.P("No dividend data available.",
                   style={"fontStyle": "italic", "color": "var(--text-muted, #888)",
                          "padding": "20px"}),
        ])

    years = _available_years(dividends)

    return html.Div([
        html.H4("Income Calendar"),

        # ── Year selector ──
        html.Div([
            html.Label("Year", style={"fontWeight": "600", "marginRight": "8px",
                                       "fontSize": "14px"}),
            dcc.Dropdown(
                id="cal-year-selector",
                options=[{"label": str(y), "value": y} for y in years],
                value=dlt.currentYear,
                clearable=False,
                style={"width": "120px"},
            ),
        ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px"}),

        # ── Content populated by callback ──
        dcc.Loading(
            html.Div(id="cal-content", children=[
                Styles.skeleton_kpis(4),
                Styles.skeleton_chart(),
                Styles.skeleton_chart("200px"),
            ]),
            type="dot",
        ),
    ])


# ─────────────────────────────────────────────
# Callbacks
# ─────────────────────────────────────────────

def register_callbacks(app):
    @app.callback(
        Output("cal-content", "children"),
        [Input("cal-year-selector", "value")]
    )
    def update_calendar(year):
        year = year or dlt.currentYear
        dividends = _get_dividends()

        if dividends.empty:
            return html.P("No dividend data available.",
                          style={"color": "var(--text-muted)", "padding": "20px"})

        month_totals, month_details = _build_calendar_data(dividends, year)

        return html.Div([
            # ── KPIs ──
            _build_kpis(month_totals, dividends),

            # ── Calendar heatmaps ──
            html.Div([
                _build_heatmap(month_totals, year),
                _build_github_heatmap(dividends, year),
            ], className="grid-2"),

            # ── Upcoming dividends (next 3 months) ──
            html.H4("Upcoming Dividends", style={"marginTop": "20px"}),
            html.P("Expected payments for the next 3 months based on historical patterns.",
                   style={"fontSize": "13px", "color": "var(--text-muted, #888)",
                          "margin": "0 0 8px 0"}),
            _build_upcoming_table(month_details),

            # ── Monthly breakdown cards ──
            html.H4("Monthly Breakdown", style={"marginTop": "20px"}),
            html.P("Expected dividend income per month by holding.",
                   style={"fontSize": "13px", "color": "var(--text-muted, #888)",
                          "margin": "0 0 8px 0"}),
            _build_monthly_cards(month_details),
        ])
