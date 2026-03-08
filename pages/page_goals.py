from dash import dcc, html, Input, Output, State, ALL, ctx
import json
import Styles
import dataLoadPositions as dlp


def layout():
    return html.Div([
        html.Hr(),
        html.H4("Financial Goals Tracker"),

        # --- Add new goal ---
        html.Div([
            html.Div([
                html.Label("Goal Name"),
                dcc.Input(id="goal-name", type="text", placeholder="e.g. Emergency Fund",
                          style={"width": "100%", "padding": "6px"}),
            ], style={"width": "25%", "display": "inline-block", "padding": "10px 15px"}),
            html.Div([
                html.Label("Target Amount"),
                dcc.Input(id="goal-target", type="number", value=10000, step=1000, min=0,
                          style={"width": "100%", "padding": "6px"}),
            ], style={"width": "20%", "display": "inline-block", "padding": "10px 15px"}),
            html.Div([
                html.Label("Current Amount"),
                dcc.Input(id="goal-current", type="number", value=0, step=500, min=0,
                          style={"width": "100%", "padding": "6px"}),
            ], style={"width": "20%", "display": "inline-block", "padding": "10px 15px"}),
            html.Div([
                html.Label("Monthly Contribution"),
                dcc.Input(id="goal-monthly", type="number", value=500, step=100, min=0,
                          style={"width": "100%", "padding": "6px"}),
            ], style={"width": "20%", "display": "inline-block", "padding": "10px 15px"}),
            html.Div([
                html.Br(),
                html.Button("Add Goal", id="goal-add-btn",
                            style={"padding": "8px 20px", "backgroundColor": Styles.colorPalette[0],
                                   "color": "white", "border": "none", "borderRadius": "8px",
                                   "cursor": "pointer", "fontSize": "14px"}),
            ], style={"width": "10%", "display": "inline-block", "padding": "10px 15px",
                       "verticalAlign": "bottom"}),
        ], style={"marginBottom": "10px"}),

        # Store for goals (persisted in browser localStorage)
        dcc.Store(id="goals-store", storage_type="local", data=[]),

        html.Hr(),

        # --- Goals display ---
        html.Div(id="goals-display"),
    ])


def _build_goal_card(goal, idx):
    """Build a visual card for a single goal with progress bar."""
    name = goal.get("name", "Goal")
    target = goal.get("target", 1)
    current = goal.get("current", 0)
    monthly = goal.get("monthly", 0)

    pct = min(current / target, 1.0) if target > 0 else 0
    remaining = max(target - current, 0)
    months_to_go = int(remaining / monthly) if monthly > 0 else float("inf")
    years_to_go = months_to_go / 12 if months_to_go != float("inf") else None

    bar_color = Styles.strongGreen if pct >= 1.0 else Styles.colorPalette[0]
    status_text = "Goal reached!" if pct >= 1.0 else (
        f"{years_to_go:.1f} years to go" if years_to_go is not None else "No monthly contribution set"
    )

    # Milestone markers at 25%, 50%, 75%, 100%
    milestones = []
    for ms in [0.25, 0.50, 0.75, 1.0]:
        reached = pct >= ms
        milestones.append(html.Div(
            className=f"milestone-dot {'reached' if reached else 'pending'}",
            style={"left": f"{ms * 100}%"},
        ))

    celebration = html.Div()
    if pct >= 1.0:
        celebration = html.Div("Goal Reached!", className="goal-reached-badge")

    return html.Div([
        html.Div([
            html.H5(name, style={"margin": "0 0 5px 0"}),
            html.Div([
                html.Div(style={
                    "width": f"{pct * 100:.0f}%",
                    "height": "24px",
                    "backgroundColor": bar_color,
                    "borderRadius": "12px",
                    "transition": "width 0.3s",
                }),
                *milestones,
            ], className="progress-track"),
            html.Div([
                html.Span(f"{current:,.0f} / {target:,.0f}  ({pct:.0%})",
                          style={"fontSize": "14px", "fontWeight": "bold"}),
                html.Span(f"  |  {status_text}",
                          style={"fontSize": "13px", "color": "#666"}),
            ]),
            celebration,
        ], style={"padding": "15px"}),
    ], className="card", style={
        "width": "30%",
        "display": "inline-block",
        "verticalAlign": "top",
        "marginRight": "15px",
        "marginBottom": "15px",
    })


def register_callbacks(app):
    @app.callback(
        Output("goals-store", "data"),
        [Input("goal-add-btn", "n_clicks")],
        [State("goal-name", "value"),
         State("goal-target", "value"),
         State("goal-current", "value"),
         State("goal-monthly", "value"),
         State("goals-store", "data")]
    )
    def add_goal(n_clicks, name, target, current, monthly, existing_goals):
        if not n_clicks or not name:
            return existing_goals or []

        goals = existing_goals or []
        goals.append({
            "name": name,
            "target": target or 0,
            "current": current or 0,
            "monthly": monthly or 0,
        })
        return goals

    @app.callback(
        Output("goals-display", "children"),
        [Input("goals-store", "data")]
    )
    def render_goals(goals):
        if not goals:
            return html.P("No goals set yet. Add a goal above to start tracking.",
                          style={"color": "#888", "fontStyle": "italic"})

        # Summary KPIs
        total_target = sum(g.get("target", 0) for g in goals)
        total_current = sum(g.get("current", 0) for g in goals)
        total_monthly = sum(g.get("monthly", 0) for g in goals)
        overall_pct = total_current / total_target if total_target > 0 else 0

        kpis = html.Div([
            Styles.kpiboxes("Total Goal Target", f"{total_target:,.0f}", Styles.colorPalette[0]),
            Styles.kpiboxes("Total Saved", f"{total_current:,.0f}", Styles.colorPalette[1]),
            Styles.kpiboxes("Monthly Savings", f"{total_monthly:,.0f}", Styles.colorPalette[2]),
            Styles.kpiboxes("Overall Progress", f"{overall_pct:.0%}", Styles.colorPalette[3]),
        ])

        cards = [_build_goal_card(g, i) for i, g in enumerate(goals)]

        return html.Div([
            kpis,
            html.Hr(),
            html.Div(cards),
        ])
