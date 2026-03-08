from dash import html


def render_page_content():
    return html.Div(children=[
        html.Div([html.H1('About This Finance Dashboard')], style={"textAlign": "left"}),
        html.Hr(),
        html.H2('Your Personal Wealth Analysis Tool'),
        html.P(
            'This application provides a comprehensive view of your personal wealth, '
            'investment portfolio, transaction history, and financial projections. '
            'Track positions, analyze dividends, run Monte Carlo simulations, model real estate, '
            'plan rebalancing, and track your financial goals — all in one place.'
        ),
        html.Hr(),
        html.H2('Pages'),
        html.P('Net Worth: Aggregate view of all assets (portfolio, real estate, cash, pension) '
               'with interactive inputs and composition charts.'),
        html.P('Positions: Holdings table with sorting/filtering, asset allocation pies '
               '(by type, geography, currency), and historical price charts.'),
        html.P('Transactions: Dividend and investment tracking with year-over-year comparisons, '
               'dividend income by holding, monthly trends, and estimated yields.'),
        html.P('Analytics: Portfolio Sharpe ratio, normalized benchmark performance, '
               'P&L by holding, return %, currency impact analysis, and ETF expense ratio tracking.'),
        html.P('Projections: Monte Carlo portfolio simulation with configurable expected return, '
               'volatility, and time horizon.'),
        html.P('Real Estate: Property appreciation, rental income, and cost projections '
               'over a customizable time period.'),
        html.P('Rebalancing: Current vs target allocation comparison with suggested trades '
               'to bring the portfolio back in line.'),
        html.P('Tax Lots: FIFO-based cost basis analysis from transaction history, '
               'showing gain/loss per lot and by symbol.'),
        html.P('Goals: Set and track financial goals with progress bars, '
               'monthly contribution projections, and estimated completion dates.'),
        html.Hr(),
        html.H2('Getting Started'),
        html.P('1. Export your positions and transactions as CSV files from your broker.'),
        html.P('2. Place them in the data/ directory or upload via the Positions page.'),
        html.P('3. Explore your portfolio insights across the dashboard pages.'),
        html.Hr(),

    ], style={"width": "50%", "textAlign": "left"})
