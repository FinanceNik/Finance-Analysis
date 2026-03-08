from dash import html


def render_page_content():
    return html.Div(children=[
        html.Div([html.H1('About This Finance Dashboard')], style={"textAlign": "left"}),
        html.Hr(),
        html.H2('Your Personal Finance Overview'),
        html.P(
            'This application provides a comprehensive view of your investment portfolio, '
            'transaction history, and financial projections. Track your positions, analyze '
            'dividends and investments, run Monte Carlo simulations, and model real estate scenarios '
            '— all in one place.'
        ),
        html.Hr(),
        html.H2('Key Features'),
        html.P('Portfolio Positions: View your holdings, asset allocation by type and geography, '
               'unrealized gains/losses, and overall portfolio performance.'),
        html.P('Transaction Analysis: Track dividends, investments, securities lending income, '
               'and fees with year-over-year comparisons.'),
        html.P('Monte Carlo Projections: Simulate future portfolio growth using configurable '
               'expected returns, volatility, and time horizons.'),
        html.P('Real Estate Modeling: Project property appreciation, rental income, and costs '
               'over a customizable time period.'),
        html.Hr(),
        html.H2('Getting Started'),
        html.P('1. Export your positions and transactions as CSV files from your broker.'),
        html.P('2. Upload them via the file upload on the Positions page.'),
        html.P('3. Explore your portfolio insights across the dashboard pages.'),
        html.Hr(),

    ], style={"width": "40%", "textAlign": "left"})
