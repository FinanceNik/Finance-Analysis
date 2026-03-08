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
        style_table={"overflowX": "auto"},
        style_cell={"padding": "8px", "textAlign": "left", "fontSize": "14px"},
        style_header={"backgroundColor": Styles.colorPalette[0], "color": "white",
                       "fontWeight": "bold", "fontSize": "14px"},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f9f9f9"},
        ],
    )


def layout():
    df = dlp.fetch_data()

    return html.Div([
        html.Hr(),

        # --- File upload ---
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
                    'borderRadius': '5px', 'textAlign': 'center',
                    'margin': '10px 0'
                },
                multiple=False
            ),
            html.Div(id='upload-status', style={'color': 'green', 'fontSize': '14px'}),
        ]),

        html.Hr(),

        # --- KPI boxes ---
        html.Div([
            Styles.kpiboxes('Total Value:',
                            f"{dlp.portfolio_total_value():,}",
                            Styles.colorPalette[0]),
            Styles.kpiboxes('Total Pur.-Cost:',
                            f"{dlp.portfolio_cost_basis():,}",
                            Styles.colorPalette[1]),
            Styles.kpiboxes('Total Unr. Gains:',
                            f"{dlp.portfolio_unrealized_pnl():,}",
                            Styles.colorPalette[2]),
            Styles.kpiboxes('Total % Return:',
                            f"{dlp.portfolio_return_pct():.1%}",
                            Styles.colorPalette[3]),
        ]),
        html.Hr(),

        # --- Interactive Holdings Table ---
        html.H4("Holdings"),
        html.Div([
            _build_holdings_table(df),
        ], style={**Styles.STYLE(100), "marginBottom": "20px"}),
        html.Hr(),

        # --- Charts row ---
        html.Div([''], style=Styles.FILLER()),
        html.Div([
            html.H4(f"{dlp.currentYear}"),
            dcc.Graph(
                id='asset-type-pie',
                figure={
                    'data': [{
                        'type': 'pie',
                        'labels': dlp.allocation_by_asset_type()['asset_type'].tolist(),
                        'values': dlp.allocation_by_asset_type()['weight'].tolist(),
                        'textinfo': 'label+percent',
                        'hoverinfo': 'label+value+percent',
                        'marker': {'colors': Styles.colorPalette},
                    }],
                    'layout': {
                        'title': f'Asset Type Allocation in {dlp.currentYear}',
                        'margin': {'t': 30, 'b': 30, 'l': 30, 'r': 30},
                    }
                }
            )
        ], style=Styles.STYLE(30)),
        html.Div([''], style=Styles.FILLER()),
        html.Div([
            html.H4(f"{dlp.currentYear}"),
            dcc.Graph(
                id='geography-pie',
                figure={
                    'data': [{
                        'type': 'pie',
                        'labels': dlp.allocation_by_geography()['geography'].tolist(),
                        'values': dlp.allocation_by_geography()['weight'].tolist(),
                        'textinfo': 'label+percent',
                        'hoverinfo': 'label+value+percent',
                        'marker': {'colors': Styles.colorPalette},
                    }],
                    'layout': {
                        'title': f'Geography Allocation in {dlp.currentYear}',
                        'margin': {'t': 30, 'b': 30, 'l': 30, 'r': 30},
                    }
                }
            )
        ], style=Styles.STYLE(30)),
        html.Div([''], style=Styles.FILLER()),
        html.Div([
            html.H4(f"{dlp.currentYear}"),
            dcc.Graph(
                id='currency-pie',
                figure={
                    'data': [{
                        'type': 'pie',
                        'labels': dlp.allocation_by_currency()['currency'].tolist(),
                        'values': dlp.allocation_by_currency()['weight'].tolist(),
                        'textinfo': 'label+percent',
                        'hoverinfo': 'label+value+percent',
                        'marker': {'colors': Styles.colorPalette},
                    }],
                    'layout': {
                        'title': f'Currency Exposure in {dlp.currentYear}',
                        'margin': {'t': 30, 'b': 30, 'l': 30, 'r': 30},
                    }
                }
            )
        ], style=Styles.STYLE(30)),
        html.Hr(),

        # --- Historical price chart ---
        html.Div([
            dcc.Graph(id='historical-prices-chart')
        ], style=Styles.STYLE(100))
    ])


def register_callbacks(app):
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
        try:
            df = pd.read_csv("data/historical_data.csv")
        except FileNotFoundError:
            return {'data': [], 'layout': {'title': 'No historical data available'}}

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
            'layout': {
                'title': 'Historical Prices (log scale)',
                'xaxis': {'title': 'Date', 'type': 'date' if 'date' in df.columns else 'linear'},
                'yaxis': {'title': 'Log Price'},
                'margin': {'t': 40, 'b': 40, 'l': 40, 'r': 40},
            }
        }
