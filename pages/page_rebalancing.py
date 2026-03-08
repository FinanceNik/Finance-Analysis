from dash import dcc, html, Input, Output, State, ALL, callback_context
import Styles
import config
import dataLoadPositions as dlp
import user_settings


def layout():
    df = dlp.fetch_data()
    if df.empty or "geography" not in df.columns:
        return html.Div([
            html.Hr(),
            html.H4("No portfolio data available for rebalancing."),
        ])

    # Build current allocation
    total = dlp.portfolio_total_value()
    alloc = df.groupby("geography")["total_value"].sum().reset_index()
    alloc["current_pct"] = (alloc["total_value"] / total * 100).round(1)

    # Get all geographies (from current + targets)
    all_geos = sorted(set(alloc["geography"].tolist()) | set(config.DEFAULT_TARGET_ALLOCATION.keys()))

    # Load saved targets
    saved_targets = user_settings.get("rebal_targets", {})

    # Build input fields for target allocation
    target_inputs = []
    for geo in all_geos:
        saved_val = saved_targets.get(geo)
        default = saved_val if saved_val is not None else config.DEFAULT_TARGET_ALLOCATION.get(geo, 0)
        target_inputs.append(
            html.Div([
                html.Label(geo),
                dcc.Input(
                    id={"type": "rebal-target", "geo": geo},
                    type="number", value=default, min=0, max=100,
                    style={"width": "60px", "padding": "4px", "marginLeft": "8px"},
                ),
                html.Span("%", style={"marginLeft": "4px"}),
            ], style={"display": "inline-block", "padding": "5px 15px"})
        )

    return html.Div([
        html.Hr(),
        html.H4("Portfolio Rebalancing Tool"),

        # Target allocation inputs
        html.Div([
            html.H5("Set Target Allocation"),
            html.Div(target_inputs),
        ], style={"marginBottom": "20px"}),

        html.Hr(),

        # Results
        html.Div(id="rebal-results"),
    ])


def register_callbacks(app):
    @app.callback(
        Output("rebal-results", "children"),
        [Input({"type": "rebal-target", "geo": ALL}, "value")]
    )
    def update_rebalancing(target_values):
        df = dlp.fetch_data()
        if df.empty or "geography" not in df.columns:
            return html.P("No data available.")

        total = dlp.portfolio_total_value()
        alloc = df.groupby("geography")["total_value"].sum().to_dict()

        # Build targets from the actual input values
        triggered = callback_context.inputs_list[0]
        targets = {}
        for item in triggered:
            geo = item["id"]["geo"]
            val = item.get("value", 0) or 0
            targets[geo] = val

        # Save targets persistently
        user_settings.save({"rebal_targets": targets})

        all_geos = sorted(set(list(alloc.keys()) + list(targets.keys())))

        rows = []
        for geo in all_geos:
            current_val = alloc.get(geo, 0)
            current_pct = current_val / total * 100 if total > 0 else 0
            target_pct = targets.get(geo, 0)
            target_val = total * target_pct / 100
            diff_val = target_val - current_val
            diff_pct = target_pct - current_pct

            rows.append({
                "geo": geo,
                "current_val": current_val,
                "current_pct": current_pct,
                "target_pct": target_pct,
                "target_val": target_val,
                "diff_val": diff_val,
                "diff_pct": diff_pct,
            })

        # Current vs Target bar chart
        geos = [r["geo"] for r in rows]
        current_pcts = [r["current_pct"] for r in rows]
        target_pcts = [r["target_pct"] for r in rows]

        comparison_chart = {
            'data': [
                {
                    'type': 'bar',
                    'x': geos,
                    'y': current_pcts,
                    'name': 'Current',
                    'marker': {'color': Styles.colorPalette[0]},
                    'text': [f"{v:.1f}%" for v in current_pcts],
                    'textposition': 'outside',
                },
                {
                    'type': 'bar',
                    'x': geos,
                    'y': target_pcts,
                    'name': 'Target',
                    'marker': {'color': Styles.colorPalette[1]},
                    'text': [f"{v:.1f}%" for v in target_pcts],
                    'textposition': 'outside',
                },
            ],
            'layout': Styles.graph_layout(
                title='Current vs Target Allocation',
                barmode='group',
                yaxis={'title': 'Allocation (%)'},
            )
        }

        # Trade suggestions
        diffs = [r["diff_val"] for r in rows]
        diff_colors = [Styles.strongGreen if v >= 0 else Styles.strongRed for v in diffs]

        trade_chart = {
            'data': [{
                'type': 'bar',
                'x': geos,
                'y': [round(d) for d in diffs],
                'marker': {'color': diff_colors},
                'text': [f"{'Buy' if d > 0 else 'Sell'} {abs(d):,.0f}" for d in diffs],
                'textposition': 'outside',
            }],
            'layout': Styles.graph_layout(
                title='Suggested Trades to Rebalance',
                yaxis={'title': 'Amount to Buy (+) / Sell (-)'},
            )
        }

        # Drift indicator
        total_drift = sum(abs(r["diff_pct"]) for r in rows) / 2
        drift_color = Styles.strongGreen if total_drift < 5 else (
            Styles.colorPalette[3] if total_drift < 10 else Styles.strongRed
        )

        return html.Div([
            html.Div([
                Styles.kpiboxes("Portfolio Value", f"{total:,}", Styles.colorPalette[0]),
                Styles.kpiboxes("Total Drift", f"{total_drift:.1f}%", drift_color),
            ]),
            html.Hr(),
            html.Div([
                dcc.Graph(id='rebal-comparison-chart', figure=comparison_chart)
            ], className="card", style=Styles.STYLE(48)),
            html.Div([''], style=Styles.FILLER()),
            html.Div([
                dcc.Graph(id='rebal-trade-chart', figure=trade_chart)
            ], className="card", style=Styles.STYLE(48)),
        ])
