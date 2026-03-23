import base64
import os
import Styles
import dataLoadPositions as dlp
from dash import dcc, html, Input, Output, State, dash_table
import pandas as pd

def _build_holdings_table(df):
    """Build an interactive DataTable of all holdings."""
    if df.empty:
        return html.P("No holdings data available.")

    display_cols = []
    col_names = {
        "symbol": "Symbol", "name": "Name", "asset_type": "Type",
        "quantity": "Qty", "price": "Price", "unit_cost": "Cost",
        "total_value": "Value", "currency": "CCY", "geography": "Geo",
        "account_id": "Account",
    }
    for col, label in col_names.items():
        if col in df.columns:
            display_cols.append({"name": label, "id": col,
                                 "type": "numeric" if col in ("quantity", "price", "unit_cost", "total_value") else "text"})

    table_data = df.to_dict("records")

    return dash_table.DataTable(
        id="holdings-table",
        columns=display_cols,
        data=table_data,
        sort_action="native",
        filter_action="native",
        page_size=20,
        fixed_rows={"headers": True},
        export_format="csv",
        export_headers="display",
        style_table={"overflowX": "auto", "overflowY": "auto", "maxHeight": "600px"},
        style_cell={"padding": "8px", "textAlign": "left", "fontSize": "14px"},
        style_header={"backgroundColor": Styles.colorPalette[0], "color": "white",
                       "fontWeight": "bold", "fontSize": "14px",
                       "fontFamily": Styles.GRAPH_LAYOUT['font']['family']},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "var(--table-stripe, #f9f9f9)"},
        ],
    )

def layout():
    account_ids = dlp.get_all_account_ids()
    account_options = [{"label": "All Accounts", "value": "ALL"}] + [
        {"label": f"Account {aid}", "value": aid} for aid in account_ids
    ]

    return html.Div([

        # --- Account filter + File upload row ---
        html.Div([
            html.Div([
                html.Label("Account"),
                dcc.Dropdown(
                    id="account-filter",
                    options=account_options,
                    value="ALL",
                    clearable=False,
                    style={"width": "200px"},
                ),
            ], style={"display": "inline-block", "verticalAlign": "top", "padding": "10px 15px"}),
            html.Div([
                dcc.Upload(
                    id='upload-positions',
                    children=html.Div([
                        'Drag & Drop or ',
                        html.A('Select a Positions CSV', style={'fontWeight': 'bold', 'cursor': 'pointer'})
                    ]),
                    style={
                        'width': '100%', 'height': '50px', 'lineHeight': '50px',
                        'borderWidth': '1px', 'borderStyle': 'dashed',
                        'borderRadius': '12px', 'textAlign': 'center',
                    },
                    multiple=False
                ),
                html.Div(id='upload-status', style={'color': 'green', 'fontSize': '14px'}),
            ], style={"display": "inline-block", "width": "60%", "verticalAlign": "top", "padding": "10px 15px"}),
        ]),

        # --- Dynamic content filtered by account ---
        dcc.Loading(
            html.Div(id="positions-content", children=html.Div([
                Styles.skeleton_kpis(4), Styles.skeleton_table(),
            ])),
            type="dot"),

        # --- Historical price chart ---
        html.Div([
            dcc.Loading(
                dcc.Graph(id='historical-prices-chart'),
                type="dot",
            )
        ], className="card")
    ])

def register_callbacks(app):
    @app.callback(
        Output("positions-content", "children"),
        [Input("account-filter", "value")]
    )
    def update_positions_view(account):
        df = dlp.fetch_data()
        if df.empty:
            return html.P("No positions data available.")

        # Filter by account if not "ALL"
        if account and account != "ALL" and "account_id" in df.columns:
            df = df[df["account_id"] == account]

        total = df["total_value"].sum() if not df.empty else 0
        cost = (df["quantity"] * df["unit_cost"]).sum() if not df.empty else 0
        pnl = total - cost
        ret_pct = pnl / cost if cost != 0 else 0

        # Allocation breakdowns
        at_alloc = df.groupby("asset_type")["total_value"].sum().reset_index()
        at_alloc["weight"] = at_alloc["total_value"] / total if total > 0 else 0

        geo_alloc = pd.DataFrame(columns=["geography", "weight"])
        if "geography" in df.columns:
            geo_alloc = df.groupby("geography")["total_value"].sum().reset_index()
            geo_alloc["weight"] = geo_alloc["total_value"] / total if total > 0 else 0

        ccy_alloc = pd.DataFrame(columns=["currency", "weight"])
        if "currency" in df.columns:
            ccy_alloc = df.groupby("currency")["total_value"].sum().reset_index()
            ccy_alloc["weight"] = ccy_alloc["total_value"] / total if total > 0 else 0

        return html.Div([
            # KPI boxes
            html.Div([
                Styles.kpiboxes('Total Value', f"{int(total):,}", Styles.colorPalette[0]),
                Styles.kpiboxes('Total Pur.-Cost', f"{int(cost):,}", Styles.colorPalette[1]),
                Styles.kpiboxes('Total Unr. Gains', f"{int(pnl):,}", Styles.colorPalette[2]),
                Styles.kpiboxes('Total % Return', f"{ret_pct:.1%}", Styles.colorPalette[3]),
            ], className="kpi-row"),

            # Holdings table
            html.H4("Holdings"),
            html.Div([
                _build_holdings_table(df),
            ], className="card", style={"marginBottom": "20px"}),

            # Charts row
            html.Div([
                html.Div([
                    dcc.Graph(
                        figure={
                            'data': [{
                                'type': 'pie',
                                'labels': at_alloc['asset_type'].tolist(),
                                'values': at_alloc['weight'].tolist(),
                                'textinfo': 'label+percent',
                                'hoverinfo': 'label+value+percent',
                                'hole': 0.35,
                                'marker': {'colors': Styles.colorPalette},
                            }],
                            'layout': Styles.graph_layout(title='Asset Type Allocation')
                        }
                    )
                ], className="card"),
                html.Div([
                    dcc.Graph(
                        figure={
                            'data': [{
                                'type': 'pie',
                                'labels': geo_alloc['geography'].tolist() if not geo_alloc.empty else [],
                                'values': geo_alloc['weight'].tolist() if not geo_alloc.empty else [],
                                'textinfo': 'label+percent',
                                'hoverinfo': 'label+value+percent',
                                'hole': 0.35,
                                'marker': {'colors': Styles.colorPalette},
                            }],
                            'layout': Styles.graph_layout(title='Geography Allocation')
                        }
                    )
                ], className="card"),
                html.Div([
                    dcc.Graph(
                        figure={
                            'data': [{
                                'type': 'pie',
                                'labels': ccy_alloc['currency'].tolist() if not ccy_alloc.empty else [],
                                'values': ccy_alloc['weight'].tolist() if not ccy_alloc.empty else [],
                                'textinfo': 'label+percent',
                                'hoverinfo': 'label+value+percent',
                                'hole': 0.35,
                                'marker': {'colors': Styles.colorPalette},
                            }],
                            'layout': Styles.graph_layout(title='Currency Exposure')
                        }
                    )
                ], className="card"),
            ], className="grid-3"),
        ])

    @app.callback(
        Output("upload-status", "children"),
        [Input("upload-positions", "contents")],
        [State("upload-positions", "filename")]
    )
    def handle_upload(contents, filename):
        if contents is None:
            return ""
        try:
            content_type, content_string = contents.split(',')
            decoded = base64.b64decode(content_string)
            safe_name = os.path.basename(filename)
            if safe_name.endswith('.csv'):
                save_path = os.path.join("data", safe_name)
                with open(save_path, 'wb') as f:
                    f.write(decoded)
                dlp.set_positions_filepath(save_path)
                return f"Uploaded: {safe_name}. Refresh the page to see updated data."
            else:
                return "Please upload a CSV file."
        except Exception as e:
            return f"Error processing file: {e}"

    @app.callback(
        Output("historical-prices-chart", "figure"),
        [Input("url", "pathname")]
    )
    def update_historical_chart(_):
        df = dlp.load_historical_data()
        if df.empty:
            return {'data': [], 'layout': Styles.graph_layout(title='No historical data available')}
        df = df.reset_index()

        # Use date column if present, otherwise fall back to index
        x_values = df["date"].tolist() if "date" in df.columns else df.index.tolist()
        data_cols = [c for c in df.columns if c != "date"]

        traces = [
            {
                'x': x_values,
                'y': df[col].tolist(),
                'type': 'scatter',
                'mode': 'lines',
                'name': col,
            } for col in data_cols
        ]
        return {
            'data': traces,
            'layout': Styles.graph_layout(
                title='Historical Prices',
                xaxis={'title': 'Date', 'type': 'date' if 'date' in df.columns else 'linear'},
                yaxis={'title': 'Price'},
            )
        }
