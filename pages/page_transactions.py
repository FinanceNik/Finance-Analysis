import Styles
import dataLoadTransactions as dlt
from dash import dcc, html

def render_page_content():
    return html.Div([
        html.Hr(),
        html.Div([
            Styles.kpiboxes(f'Total Dividends:',
                            dlt.total_transaction_amount(dlt.currentYear, "Dividend"),
                            Styles.colorPalette[0]),
            Styles.kpiboxes(f'Total New Investments:',
                            dlt.total_transaction_amount(dlt.currentYear, "Payment"),
                            Styles.colorPalette[1]),
            Styles.kpiboxes(f'Total Sec. Lending:',
                            dlt.total_transaction_amount(dlt.currentYear, "Securities Lending"),
                            Styles.colorPalette[2]),
            Styles.kpiboxes(f'Total Fees:',
                            dlt.total_transaction_amount(dlt.currentYear, "Custody Fees"),
                            Styles.colorPalette[3]),
        ]),
        html.Hr(),
        html.Div([
            html.H4(f"Yearly Investments"),
            dcc.Graph(
                id='monthly-investment-bar',
                figure={
                    'data': [
                        {
                            'x': dlt.yearly_transaction_summary()[0],
                            'y': dlt.yearly_transaction_summary()[1],
                            'type': 'bar',
                            'name': str(dlt.currentYear - 1),
                            'marker': {'color': Styles.colorPalette[1]}
                        },
                    ],
                    'layout': {
                        'barmode': 'group',
                        'title': 'Monthly Investment Comparison',
                        'xaxis': {'title': 'Month'},
                        'yaxis': {'title': 'Investments'},
                        'margin': {'t': 40, 'b': 40, 'l': 40, 'r': 40},
                    }
                }
            )
        ], style=Styles.STYLE(100)),
        html.Hr(),
        html.Div([
            html.H4(f"Monthly Dividends: {dlt.currentYear - 1} vs {dlt.currentYear}"),
            dcc.Graph(
                id='monthly-dividends-bar',
                figure={
                    'data': [
                        {
                            'x': dlt.months,
                            'y': dlt.monthly_totals("Dividend")[1],
                            'type': 'bar',
                            'name': str(dlt.currentYear - 1),
                            'marker': {'color': Styles.colorPalette[1]}
                        },
                        {
                            'x': dlt.months,
                            'y': dlt.monthly_totals("Dividend")[2],
                            'type': 'bar',
                            'name': str(dlt.currentYear),
                            'marker': {'color': Styles.colorPalette[0]}
                        },
                    ],
                    'layout': {
                        'barmode': 'group',
                        'title': 'Monthly Dividends Comparison',
                        'xaxis': {'title': 'Month'},
                        'yaxis': {'title': 'Dividends Paid'},
                        'margin': {'t': 40, 'b': 40, 'l': 40, 'r': 40},
                    }
                }
            )
        ],style=Styles.STYLE(80)),
        html.Div([''], style=Styles.FILLER()),
        html.Div([
            html.H4(f"Annual"),
            dcc.Graph(
                id='yearly-dividends-bar',
                figure={
                    'data': [
                        {
                            'x': [str(dlt.currentYear - 1), str(dlt.currentYear)],
                            'y': dlt.totals("Dividend"),
                            'type': 'bar',
                            'marker': {'color': [Styles.colorPalette[1], Styles.colorPalette[0]]},
                            'name': 'Yearly Dividend'
                        }
                    ],
                    'layout': {
                        'xaxis': {'title': 'Year'},
                        'yaxis': {'title': 'Dividend Total'},
                        'margin': {'t': 40, 'b': 40, 'l': 40, 'r': 40},
                    }
                }
            )
        ],style=Styles.STYLE(18)),
        # --------------------------------------------------------------------------------------------------------------
        html.Hr(),
        html.Div([
            html.H4(f"Monthly Investments: {dlt.currentYear - 1} vs {dlt.currentYear}"),
            dcc.Graph(
                id='monthly-investment-bar',
                figure={
                    'data': [
                        {
                            'x': dlt.months,
                            'y': dlt.monthly_totals("Payment")[1],
                            'type': 'bar',
                            'name': str(dlt.currentYear - 1),
                            'marker': {'color': Styles.colorPalette[1]}
                        },
                        {
                            'x': dlt.months,
                            'y': dlt.monthly_totals("Payment")[2],
                            'type': 'bar',
                            'name': str(dlt.currentYear),
                            'marker': {'color': Styles.colorPalette[0]}
                        },
                    ],
                    'layout': {
                        'barmode': 'group',
                        'title': 'Monthly Investment Comparison',
                        'xaxis': {'title': 'Month'},
                        'yaxis': {'title': 'Investments'},
                        'margin': {'t': 40, 'b': 40, 'l': 40, 'r': 40},
                    }
                }
            )
        ], style=Styles.STYLE(80)),
        html.Div([''], style=Styles.FILLER()),
        html.Div([
            html.H4(f"Annual"),
            dcc.Graph(
                id='yearly-investment-bar',
                figure={
                    'data': [
                        {
                            'x': [str(dlt.currentYear - 1), str(dlt.currentYear)],
                            'y': dlt.totals("Payment"),
                            'type': 'bar',
                            'marker': {'color': [Styles.colorPalette[1], Styles.colorPalette[0]]},
                            'name': 'Yearly Investments'
                        }
                    ],
                    'layout': {
                        'xaxis': {'title': 'Year'},
                        'yaxis': {'title': 'Investment Total'},
                        'margin': {'t': 40, 'b': 40, 'l': 40, 'r': 40},
                    }
                }
            )
        ], style=Styles.STYLE(18))
    ])

