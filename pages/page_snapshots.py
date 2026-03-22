import json
from pathlib import Path
from datetime import datetime

import pandas as pd
from dash import dcc, html, Input, Output, State, dash_table, callback_context

import Styles
import dataLoadPositions as dlp

SNAPSHOTS_FILE = Path("data/snapshots.json")


def _load_snapshots() -> list:
    """Load snapshots from JSON file, creating it if it doesn't exist."""
    if not SNAPSHOTS_FILE.exists():
        SNAPSHOTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOTS_FILE.write_text("[]")
        return []
    try:
        data = json.loads(SNAPSHOTS_FILE.read_text())
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_snapshots(snapshots: list):
    """Persist snapshots list to JSON file."""
    SNAPSHOTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS_FILE.write_text(json.dumps(snapshots, indent=2))


def _take_snapshot() -> dict:
    """Capture current portfolio state as a snapshot dict."""
    df = dlp.fetch_data()
    total_value = dlp.portfolio_total_value()
    num_positions = len(df) if not df.empty else 0

    # Top 5 holdings by weight
    top5 = []
    if not df.empty and "total_value" in df.columns and total_value > 0:
        top = df.nlargest(5, "total_value")
        name_col = "name" if "name" in top.columns else "symbol"
        for _, row in top.iterrows():
            pct = round(row["total_value"] / total_value * 100, 2)
            top5.append({"name": row.get(name_col, "Unknown"), "pct": pct})

    # Cash position
    cash = 0.0
    if not df.empty and "asset_type" in df.columns:
        cash_rows = df[df["asset_type"].str.lower().str.contains("cash", na=False)]
        if not cash_rows.empty:
            cash = float(cash_rows["total_value"].sum())

    # Allocation breakdowns
    geo_alloc = {}
    if not df.empty and "geography" in df.columns and total_value > 0:
        geo = df.groupby("geography")["total_value"].sum()
        geo_alloc = {k: round(v / total_value * 100, 2) for k, v in geo.items()}

    sector_alloc = {}
    if not df.empty and "asset_type" in df.columns and total_value > 0:
        sec = df.groupby("asset_type")["total_value"].sum()
        sector_alloc = {k: round(v / total_value * 100, 2) for k, v in sec.items()}

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "portfolio_value": total_value,
        "num_positions": num_positions,
        "top5": top5,
        "cash": cash,
        "geo_allocation": geo_alloc,
        "sector_allocation": sector_alloc,
    }


def _build_history_table(snapshots):
    """Build a DataTable showing snapshot history with change columns."""
    if not snapshots:
        return html.P("No snapshots yet. Click 'Take Snapshot' to capture your first one.")

    rows = []
    for i, snap in enumerate(snapshots):
        val = snap.get("portfolio_value", 0)
        prev_val = snapshots[i - 1].get("portfolio_value", 0) if i > 0 else None
        change_pct = round((val - prev_val) / prev_val * 100, 2) if prev_val else None
        change_abs = round(val - prev_val, 0) if prev_val is not None else None
        rows.append({
            "date": snap.get("date", ""),
            "portfolio_value": f"{int(val):,}",
            "num_positions": snap.get("num_positions", 0),
            "change_pct": f"{change_pct:+.2f}%" if change_pct is not None else "-",
            "change_abs": f"{int(change_abs):+,}" if change_abs is not None else "-",
        })

    columns = [
        {"name": "Date", "id": "date"},
        {"name": "Portfolio Value", "id": "portfolio_value"},
        {"name": "# Positions", "id": "num_positions"},
        {"name": "Change (%)", "id": "change_pct"},
        {"name": "Change ($)", "id": "change_abs"},
    ]

    return dash_table.DataTable(
        id="snapshots-history-table",
        columns=columns,
        data=rows,
        sort_action="native",
        page_size=20,
        fixed_rows={"headers": True},
        export_format="csv",
        export_headers="display",
        style_table={"overflowX": "auto", "overflowY": "auto", "maxHeight": "500px"},
        style_cell={"padding": "8px", "textAlign": "left", "fontSize": "14px"},
        style_header={"fontWeight": "bold", "fontSize": "14px",
                       "fontFamily": Styles.GRAPH_LAYOUT['font']['family']},
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "var(--table-stripe, #f9f9f9)"},
        ],
    )


def _build_value_chart(snapshots):
    """Line chart of portfolio value over time."""
    if len(snapshots) < 1:
        return {
            'data': [],
            'layout': Styles.graph_layout(
                title='',
                annotations=[{'text': 'No snapshots yet', 'showarrow': False,
                               'font': {'size': 14}}],
            ),
        }

    dates = [s["date"] for s in snapshots]
    values = [s["portfolio_value"] for s in snapshots]

    return {
        'data': [{
            'x': dates,
            'y': values,
            'type': 'scatter',
            'mode': 'lines+markers',
            'name': 'Portfolio Value',
            'line': {'color': Styles.colorPalette[0], 'width': 3},
            'marker': {'size': 8},
            'fill': 'tozeroy',
            'fillcolor': f'rgba(55, 63, 81, 0.1)',
        }],
        'layout': Styles.graph_layout(
            title='',
            xaxis={'title': 'Date', 'type': 'date'},
            yaxis={'title': 'Portfolio Value'},
            hovermode='x unified',
            margin={'t': 40, 'b': 60, 'l': 70, 'r': 30},
        ),
    }


def _build_allocation_drift_chart(snapshots):
    """Stacked area chart showing how allocation percentages changed over time."""
    if len(snapshots) < 1:
        return {
            'data': [],
            'layout': Styles.graph_layout(
                title='',
                annotations=[{'text': 'No snapshots yet', 'showarrow': False,
                               'font': {'size': 14}}],
            ),
        }

    dates = [s["date"] for s in snapshots]

    # Collect all allocation keys across snapshots
    all_keys = set()
    for s in snapshots:
        all_keys.update(s.get("sector_allocation", {}).keys())
    all_keys = sorted(all_keys)

    if not all_keys:
        return {
            'data': [],
            'layout': Styles.graph_layout(
                title='',
                annotations=[{'text': 'No allocation data', 'showarrow': False,
                               'font': {'size': 14}}],
            ),
        }

    colors = Styles.purple_list + Styles.colorPalette
    traces = []
    for i, key in enumerate(all_keys):
        y_vals = [s.get("sector_allocation", {}).get(key, 0) for s in snapshots]
        traces.append({
            'x': dates,
            'y': y_vals,
            'type': 'scatter',
            'mode': 'lines',
            'name': key,
            'stackgroup': 'one',
            'line': {'color': colors[i % len(colors)], 'width': 0.5},
        })

    return {
        'data': traces,
        'layout': Styles.graph_layout(
            title='',
            xaxis={'title': 'Date', 'type': 'date'},
            yaxis={'title': 'Allocation (%)', 'range': [0, 100]},
            hovermode='x unified',
            legend={'orientation': 'h', 'y': -0.2, 'x': 0.5, 'xanchor': 'center'},
            margin={'t': 40, 'b': 80, 'l': 50, 'r': 30},
        ),
    }


def _build_kpis(snapshots):
    """Build KPI row: Latest Value, Total Snapshots, Avg Weekly Change."""
    if not snapshots:
        return html.Div([
            Styles.kpiboxes("Latest Value", "N/A", Styles.colorPalette[0]),
            Styles.kpiboxes("Total Snapshots", 0, Styles.colorPalette[1]),
            Styles.kpiboxes("Avg Weekly Change", "N/A", Styles.colorPalette[2]),
        ], className="kpi-row")

    latest_value = snapshots[-1].get("portfolio_value", 0)
    total_snapshots = len(snapshots)

    # Average change between consecutive snapshots
    changes = []
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1].get("portfolio_value", 0)
        curr = snapshots[i].get("portfolio_value", 0)
        if prev > 0:
            changes.append((curr - prev) / prev * 100)

    avg_change = sum(changes) / len(changes) if changes else 0
    change_color = Styles.strongGreen if avg_change >= 0 else Styles.strongRed

    return html.Div([
        Styles.kpiboxes("Latest Value", f"{int(latest_value):,}", Styles.colorPalette[0]),
        Styles.kpiboxes("Total Snapshots", total_snapshots, Styles.colorPalette[1]),
        Styles.kpiboxes("Avg Weekly Change", f"{avg_change:+.2f}%", change_color),
    ], className="kpi-row")


def layout():
    snapshots = _load_snapshots()

    return html.Div([
        dcc.Loading(type="circle", children=[

            # Take Snapshot button
            html.Div([
                html.Button(
                    "Take Snapshot",
                    id="take-snapshot-btn",
                    className="header-btn",
                    style={"fontSize": "15px", "padding": "10px 24px",
                           "marginBottom": "20px"},
                ),
                html.Div(id="snapshot-status", style={
                    "display": "inline-block", "marginLeft": "16px",
                    "fontSize": "14px", "color": Styles.strongGreen,
                }),
            ]),

            # KPI row
            html.Div(id="snapshot-kpis", children=_build_kpis(snapshots)),

            # Portfolio value over time chart
            html.Div([
                html.H5("Portfolio Value Over Time"),
                dcc.Graph(
                    id="snapshot-value-chart",
                    figure=_build_value_chart(snapshots),
                    config={"displayModeBar": False},
                ),
            ], className="card"),

            # Allocation drift chart
            html.Div([
                html.H5("Allocation Drift"),
                dcc.Graph(
                    id="snapshot-drift-chart",
                    figure=_build_allocation_drift_chart(snapshots),
                    config={"displayModeBar": False},
                ),
            ], className="card"),

            # Snapshot history table
            html.Div([
                html.H5("Snapshot History"),
                html.Div(id="snapshot-table-container",
                         children=_build_history_table(snapshots)),
            ], className="card"),
        ]),
    ])


def register_callbacks(app):
    @app.callback(
        [Output("snapshot-status", "children"),
         Output("snapshot-kpis", "children"),
         Output("snapshot-value-chart", "figure"),
         Output("snapshot-drift-chart", "figure"),
         Output("snapshot-table-container", "children")],
        [Input("take-snapshot-btn", "n_clicks")],
        prevent_initial_call=True,
    )
    def take_snapshot(n_clicks):
        if not n_clicks:
            snapshots = _load_snapshots()
            return (
                "",
                _build_kpis(snapshots),
                _build_value_chart(snapshots),
                _build_allocation_drift_chart(snapshots),
                _build_history_table(snapshots),
            )

        snapshots = _load_snapshots()
        new_snap = _take_snapshot()
        snapshots.append(new_snap)
        _save_snapshots(snapshots)

        timestamp = datetime.now().strftime("%H:%M:%S")
        return (
            f"Snapshot saved at {timestamp}",
            _build_kpis(snapshots),
            _build_value_chart(snapshots),
            _build_allocation_drift_chart(snapshots),
            _build_history_table(snapshots),
        )
