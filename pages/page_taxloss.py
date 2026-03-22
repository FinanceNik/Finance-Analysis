import Styles
import dataLoadPositions as dlp
from dash import dcc, html, Input, Output, State, dash_table


def _compute_losing_positions(tax_rate):
    """Return a DataFrame of positions with unrealized losses and summary metrics."""
    df = dlp.add_position_pnl_columns()
    if df.empty:
        return df, {}

    # Filter to positions with unrealized losses
    losers = df[df["unrealized_pnl"] < 0].copy()
    if losers.empty:
        return losers, {
            "total_losses": 0,
            "tax_savings": 0,
            "num_positions": 0,
            "largest_loss": 0,
        }

    losers["unrealized_loss_pct"] = losers["pnl_pct"] * 100
    losers["potential_tax_savings"] = (losers["unrealized_pnl"].abs() * tax_rate).round(2)
    losers = losers.sort_values("unrealized_pnl", ascending=True)

    total_losses = losers["unrealized_pnl"].sum()
    summary = {
        "total_losses": round(total_losses, 2),
        "tax_savings": round(abs(total_losses) * tax_rate, 2),
        "num_positions": len(losers),
        "largest_loss": round(losers["unrealized_pnl"].min(), 2),
    }

    return losers, summary


def layout():
    return html.Div([
        # Tax rate input with persistent storage
        dcc.Store(id="taxloss-rate-store", storage_type="local", data=0.25),

        html.Div([
            html.Div([
                html.Label("Marginal Tax Rate (%)",
                           style={"fontWeight": "600", "marginRight": "10px"}),
                dcc.Input(
                    id="taxloss-rate-input",
                    type="number",
                    min=0, max=100, step=0.5,
                    value=25,
                    style={"width": "100px", "padding": "6px 10px",
                           "borderRadius": "8px", "border": "1px solid var(--border, #ddd)",
                           "fontSize": "14px"},
                ),
                html.Span("  %", style={"marginLeft": "4px", "fontSize": "14px"}),
            ], style={"display": "flex", "alignItems": "center", "padding": "10px 0"}),
        ], style={"marginBottom": "8px"}),

        # Wash sale warning banner
        html.Div([
            html.Span("\u26A0 ", style={"fontSize": "18px"}),
            html.Strong("Wash Sale Rule: "),
            html.Span(
                "Remember: You cannot repurchase substantially identical securities "
                "within 30 days before or after the sale."
            ),
        ], className="card", style={
            "backgroundColor": "var(--bg-warn, #fff8e1)",
            "borderLeft": "4px solid #f5a623",
            "padding": "12px 16px",
            "marginBottom": "16px",
            "fontSize": "14px",
            "borderRadius": "8px",
        }),

        # Dynamic content area
        dcc.Loading(
            html.Div(id="taxloss-content", children=html.Div([
                Styles.skeleton_kpis(4),
                Styles.skeleton_chart("350px"),
                Styles.skeleton_table(),
            ])),
            type="dot",
        ),
    ])


def register_callbacks(app):
    # Sync stored rate into the input on page load
    app.clientside_callback(
        """
        function(stored_rate) {
            if (stored_rate !== null && stored_rate !== undefined) {
                return stored_rate * 100;
            }
            return 25;
        }
        """,
        Output("taxloss-rate-input", "value"),
        Input("taxloss-rate-store", "data"),
    )

    @app.callback(
        [Output("taxloss-content", "children"),
         Output("taxloss-rate-store", "data")],
        [Input("taxloss-rate-input", "value")],
    )
    def update_taxloss_view(rate_pct):
        if rate_pct is None or rate_pct < 0:
            rate_pct = 25
        tax_rate = rate_pct / 100.0

        losers, summary = _compute_losing_positions(tax_rate)

        if losers.empty:
            return html.Div([
                html.Div([
                    Styles.kpiboxes("Total Unrealized Losses", 0, Styles.strongRed),
                    Styles.kpiboxes("Potential Tax Savings", 0, Styles.strongGreen),
                    Styles.kpiboxes("Positions with Losses", 0, Styles.colorPalette[0]),
                    Styles.kpiboxes("Largest Single Loss", 0, Styles.strongRed),
                ], className="kpi-row"),
                html.P("No positions with unrealized losses found.",
                       style={"textAlign": "center", "padding": "40px", "fontSize": "16px",
                              "color": "var(--text-muted, #888)"}),
            ]), tax_rate

        # KPI row
        kpis = html.Div([
            Styles.kpiboxes("Total Unrealized Losses",
                            f"{summary['total_losses']:,.0f}", Styles.strongRed),
            Styles.kpiboxes("Potential Tax Savings",
                            f"{summary['tax_savings']:,.0f}", Styles.strongGreen),
            Styles.kpiboxes("Positions with Losses",
                            summary["num_positions"], Styles.colorPalette[0]),
            Styles.kpiboxes("Largest Single Loss",
                            f"{summary['largest_loss']:,.0f}", Styles.strongRed),
        ], className="kpi-row")

        # Build display table
        table_data = []
        for _, row in losers.iterrows():
            name = row.get("name", "")
            if not name or str(name) == "nan":
                name = row.get("symbol", "")
            table_data.append({
                "symbol": row["symbol"],
                "name": name,
                "quantity": round(row["quantity"], 4),
                "cost_basis": round(row["cost_basis"], 2),
                "market_value": round(row["market_value"], 2),
                "unrealized_loss": round(row["unrealized_pnl"], 2),
                "unrealized_loss_pct": round(row.get("unrealized_loss_pct", 0), 1),
                "potential_tax_savings": round(row["potential_tax_savings"], 2),
            })

        columns = [
            {"name": "Symbol", "id": "symbol"},
            {"name": "Name", "id": "name"},
            {"name": "Qty", "id": "quantity", "type": "numeric"},
            {"name": "Cost Basis", "id": "cost_basis", "type": "numeric"},
            {"name": "Current Value", "id": "market_value", "type": "numeric"},
            {"name": "Unr. Loss ($)", "id": "unrealized_loss", "type": "numeric"},
            {"name": "Unr. Loss (%)", "id": "unrealized_loss_pct", "type": "numeric"},
            {"name": "Tax Savings", "id": "potential_tax_savings", "type": "numeric"},
        ]

        table = dash_table.DataTable(
            id="taxloss-table",
            columns=columns,
            data=table_data,
            sort_action="native",
            filter_action="native",
            page_size=20,
            export_format="csv",
            export_headers="display",
            style_table={"overflowX": "auto", "maxHeight": "500px"},
            style_cell={"padding": "8px", "textAlign": "left", "fontSize": "13px"},
            style_header={"fontWeight": "bold", "fontSize": "13px",
                          "fontFamily": Styles.GRAPH_LAYOUT['font']['family']},
            style_data_conditional=[
                {"if": {"column_id": "unrealized_loss"},
                 "color": Styles.strongRed},
                {"if": {"column_id": "unrealized_loss_pct"},
                 "color": Styles.strongRed},
                {"if": {"column_id": "potential_tax_savings"},
                 "color": Styles.strongGreen, "fontWeight": "600"},
                {"if": {"row_index": "odd"},
                 "backgroundColor": "var(--table-stripe, #f9f9f9)"},
            ],
        )

        # Horizontal bar chart of harvest candidates
        chart_df = losers.sort_values("unrealized_pnl", ascending=True)
        # Color by magnitude: deeper red for larger losses
        max_loss = abs(chart_df["unrealized_pnl"].min()) if not chart_df.empty else 1
        colors = []
        for v in chart_df["unrealized_pnl"]:
            intensity = min(abs(v) / max_loss, 1.0)
            r = 255
            g = int(120 * (1 - intensity))
            b = int(100 * (1 - intensity))
            colors.append(f"rgb({r},{g},{b})")

        bar_chart = {
            "data": [{
                "type": "bar",
                "x": chart_df["unrealized_pnl"].round(2).tolist(),
                "y": chart_df["symbol"].tolist(),
                "orientation": "h",
                "marker": {"color": colors},
                "text": [f"{v:,.0f}" for v in chart_df["unrealized_pnl"]],
                "textposition": "outside",
            }],
            "layout": Styles.graph_layout(
                title="Tax-Loss Harvest Candidates",
                xaxis={"title": "Unrealized Loss ($)"},
                yaxis={"title": ""},
                margin={"l": 100, "r": 80},
                height=max(300, len(chart_df) * 35),
            ),
        }

        return html.Div([
            kpis,
            html.Hr(),

            # Harvest candidates chart
            html.H4("Harvest Candidates"),
            html.Div([
                dcc.Graph(id="taxloss-bar-chart", figure=bar_chart),
            ], className="card", style={"marginBottom": "20px"}),

            # Positions table
            html.H4("Positions with Unrealized Losses"),
            html.Div([table], className="card", style={"marginBottom": "20px"}),
        ]), tax_rate
