import pandas as pd
import Styles
import dataLoadTransactions as dlt
from dash import dcc, html, dash_table


def layout():
    y2 = dlt.currentYear - 2
    y1 = dlt.currentYear - 1
    y0 = dlt.currentYear

    net_2y = list(dlt.net_contributions_monthly(y2).values())
    net_1y = list(dlt.net_contributions_monthly(y1).values())
    net_0y = list(dlt.net_contributions_monthly(y0).values())

    yearly = [dlt.net_contributions_yearly(y) for y in (y2, y1, y0)]
    yearly_colors = [Styles.colorPalette[0] if v >= 0 else Styles.colorPalette[2]
                     for v in yearly]

    return html.Div([
        html.Div([
            Styles.kpiboxes('Net Contributions YTD',
                            dlt.net_contributions_yearly(y0),
                            Styles.colorPalette[0]),
            Styles.kpiboxes('Total Sec. Lending',
                            dlt.total_transaction_amount(y0, "Securities Lending"),
                            Styles.colorPalette[1]),
            Styles.kpiboxes('Total Fees',
                            dlt.total_transaction_amount(y0, "Custody Fees"),
                            Styles.colorPalette[2]),
        ], className="kpi-row"),

        html.Div([
            html.Div([
                dcc.Graph(
                    id='monthly-investment-comparison-bar',
                    figure={
                        'data': [
                            {
                                'x': dlt.months,
                                'y': net_2y,
                                'type': 'bar',
                                'name': str(y2),
                                'marker': {'color': Styles.colorPalette[2]}
                            },
                            {
                                'x': dlt.months,
                                'y': net_1y,
                                'type': 'bar',
                                'name': str(y1),
                                'marker': {'color': Styles.colorPalette[1]}
                            },
                            {
                                'x': dlt.months,
                                'y': net_0y,
                                'type': 'bar',
                                'name': str(y0),
                                'marker': {'color': Styles.colorPalette[0]}
                            },
                        ],
                        'layout': Styles.graph_layout(
                            barmode='group',
                            title='Monthly Net Contributions',
                            xaxis={'title': 'Month'},
                            yaxis={'title': 'Net Contributions'},
                        )
                    }
                )
            ], className="card"),
            html.Div([
                dcc.Graph(
                    id='yearly-investment-bar',
                    figure={
                        'data': [{
                            'x': [str(y2), str(y1), str(y0)],
                            'y': yearly,
                            'type': 'bar',
                            'marker': {'color': yearly_colors},
                            'name': 'Yearly Net Contributions',
                        }],
                        'layout': Styles.graph_layout(
                            title='Yearly Net Contributions',
                            xaxis={'title': 'Year'},
                            yaxis={'title': 'Net Contributions'},
                        )
                    }
                )
            ], className="card"),
        ], className="grid-80-20"),

        html.Div([
            dcc.Graph(
                id='cumulative-net-contributions',
                figure=_cumulative_contributions_figure()
            )
        ], className="card"),

        html.Div([
            _build_transactions_table()
        ], className="card"),
    ])


def _build_transactions_table():
    """Build a DataTable showing recent transactions."""
    df = dlt.ingest_transactions()
    if df.empty:
        return html.Div("No transaction data available.")

    display_cols = ['date', 'transaction', 'symbol', 'quantity', 'unit_price', 'net_amount']
    available = [c for c in display_cols if c in df.columns]
    df = df[available].copy()

    if 'date' in df.columns:
        df = df.sort_values('date', ascending=False)
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')

    columns = [{"name": c.replace('_', ' ').title(), "id": c} for c in available]

    return dash_table.DataTable(
        id="transactions-table",
        columns=columns,
        data=df.to_dict("records"),
        page_size=20,
        sort_action="native",
        filter_action="native",
        export_format="csv",
        export_headers="display",
        style_table={"overflowX": "auto", "overflowY": "auto", "maxHeight": "600px"},
        style_cell={"padding": "8px", "textAlign": "left", "fontSize": "13px"},
        style_header={
            "backgroundColor": Styles.colorPalette[0],
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "13px",
            "fontFamily": Styles.GRAPH_LAYOUT["font"]["family"],
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"},
             "backgroundColor": "var(--table-stripe, #f9f9f9)"},
        ],
    )


def _cumulative_contributions_figure():
    """Build a cumulative net contributions area chart across all time."""
    df = dlt.ingest_transactions()
    if df.empty:
        return {'data': [], 'layout': Styles.graph_layout(
            title='Cumulative Net Contributions')}

    contrib = df.loc[df['transaction'].str.lower().isin(['buy', 'sell'])].copy()
    contrib['period'] = contrib['date'].dt.to_period('M')
    monthly = (
        contrib
        .groupby('period')['net_amount']
        .sum()
        .sort_index()
    )
    # Negate so buys (negative net_amount) become positive contributions
    cumulative = (-monthly).cumsum().round(2)

    labels = [p.strftime('%b %Y') for p in cumulative.index]
    values = cumulative.tolist()

    return {
        'data': [{
            'x': labels,
            'y': values,
            'type': 'scatter',
            'mode': 'lines',
            'fill': 'tozeroy',
            'name': 'Cumulative Net Contributions',
            'line': {'color': Styles.colorPalette[0]},
        }],
        'layout': Styles.graph_layout(
            title='Cumulative Net Contributions',
            xaxis={'title': 'Month'},
            yaxis={'title': 'Cumulative Amount'},
        )
    }
