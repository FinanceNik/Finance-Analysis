import Styles
import dataLoadTransactions as dlt
from dash import dcc, html


def render_page_content():
    y2 = dlt.currentYear - 2
    y1 = dlt.currentYear - 1
    y0 = dlt.currentYear

    return html.Div([
        html.Div([
            Styles.kpiboxes('Total Investments',
                            dlt.total_transaction_amount(y0, "Payment"),
                            Styles.colorPalette[0]),
            Styles.kpiboxes('Total Sec. Lending',
                            dlt.total_transaction_amount(y0, "Securities Lending"),
                            Styles.colorPalette[1]),
            Styles.kpiboxes('Total Fees',
                            dlt.total_transaction_amount(y0, "Custody Fees"),
                            Styles.colorPalette[2]),
        ], className="kpi-row"),

        # --- Monthly Investments: 3-year comparison ---
        html.Div([
            html.Div([
                dcc.Graph(
                    id='monthly-investment-comparison-bar',
                    figure={
                        'data': [
                            {
                                'x': dlt.months,
                                'y': dlt.monthly_totals("Payment")[1],
                                'type': 'bar',
                                'name': str(y2),
                                'marker': {'color': Styles.colorPalette[2]}
                            },
                            {
                                'x': dlt.months,
                                'y': dlt.monthly_totals("Payment")[2],
                                'type': 'bar',
                                'name': str(y1),
                                'marker': {'color': Styles.colorPalette[1]}
                            },
                            {
                                'x': dlt.months,
                                'y': dlt.monthly_totals("Payment")[3],
                                'type': 'bar',
                                'name': str(y0),
                                'marker': {'color': Styles.colorPalette[0]}
                            },
                        ],
                        'layout': Styles.graph_layout(
                            barmode='group',
                            title='Monthly Investment Comparison',
                            xaxis={'title': 'Month'},
                            yaxis={'title': 'Investments'},
                        )
                    }
                )
            ], className="card"),
            html.Div([
                dcc.Graph(
                    id='yearly-investment-bar',
                    figure={
                        'data': [
                            {
                                'x': [str(y2), str(y1), str(y0)],
                                'y': dlt.totals("Payment"),
                                'type': 'bar',
                                'marker': {'color': [Styles.colorPalette[2],
                                                     Styles.colorPalette[1],
                                                     Styles.colorPalette[0]]},
                                'name': 'Yearly Investments'
                            }
                        ],
                        'layout': Styles.graph_layout(
                            xaxis={'title': 'Year'},
                            yaxis={'title': 'Investment Total'},
                        )
                    }
                )
            ], className="card"),
        ], className="grid-80-20"),
    ])
