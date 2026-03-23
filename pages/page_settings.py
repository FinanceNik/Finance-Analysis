"""Centralized Settings page — budget inputs and net worth overrides."""
from dash import dcc, html, Input, Output, State
import Styles
import user_settings


def _input_field(label, id_, value, width="18%"):
    return html.Div([
        html.Label(label, style={"fontSize": "0.85rem", "color": "var(--text-secondary)"}),
        dcc.Input(id=id_, type="number", value=value,
                  style={"width": "100%", "padding": "6px",
                         "borderRadius": "6px", "border": "1px solid var(--border-color)",
                         "backgroundColor": "var(--bg-input)", "color": "var(--text-primary)"}),
    ], style={"width": width, "display": "inline-block", "padding": "8px 12px"})


def layout():
    saved = user_settings.load()
    inc = saved.get("budget", {}).get("income", {})
    exp = saved.get("budget", {}).get("expenses", {})
    nw = saved.get("networth", {})

    return html.Div([
        html.H4("Settings"),
        html.P("Configure your budget, expenses, and net worth inputs. "
               "Changes are used across the dashboard, FIRE calculations, and projections.",
               style={"color": "var(--text-secondary)", "marginBottom": "20px"}),

        # --- Save button + feedback ---
        html.Div([
            html.Button("Save All Settings", id="settings-save-btn",
                        className="header-btn", style={"marginRight": "12px"}),
            html.Span(id="settings-save-feedback", style={"color": "var(--green)", "fontWeight": "500"}),
        ], style={"marginBottom": "24px"}),

        # ── Section 1: Monthly Income ──
        html.Div([
            html.H5("Monthly Income"),
            html.Div([
                _input_field("Salary (Monthly)", "settings-salary", inc.get("salary", 9583)),
                _input_field("Side Income", "settings-side", inc.get("side", 375)),
                _input_field("Dividend Income", "settings-dividends", inc.get("dividends", 292)),
                _input_field("Other Income", "settings-other-inc", inc.get("other", 0)),
            ]),
        ], className="card", style={"padding": "20px", "marginBottom": "16px"}),

        # ── Section 2: Monthly Expenses ──
        html.Div([
            html.H5("Monthly Expenses"),
            html.Div([
                _input_field("Rent", "settings-rent", exp.get("rent", 1680), "14%"),
                _input_field("Utilities", "settings-utilities", exp.get("utilities", 25), "14%"),
                _input_field("Health Insurance", "settings-insurance", exp.get("insurance", 320), "14%"),
                _input_field("Gebäudeversicherung", "settings-gebaeude", exp.get("gebaeude", 0), "14%"),
                _input_field("Hausnebenkosten", "settings-hausneben", exp.get("hausneben", 0), "14%"),
                _input_field("SERAFE", "settings-serafe", exp.get("serafe", 0), "14%"),
                _input_field("Phone Contract", "settings-phone", exp.get("phone", 0), "14%"),
                _input_field("Claude", "settings-claude", exp.get("claude", 0), "14%"),
                _input_field("Spotify", "settings-spotify", exp.get("spotify", 0), "14%"),
                _input_field("Food & Groceries", "settings-food", exp.get("food", 0), "14%"),
                _input_field("Transport", "settings-transport", exp.get("transport", 0), "14%"),
                _input_field("Entertainment", "settings-entertainment", exp.get("entertainment", 0), "14%"),
                _input_field("Leibrente", "settings-leibrente", exp.get("leibrente", 1200), "14%"),
                _input_field("Taxes", "settings-taxes", exp.get("taxes", 0), "14%"),
                _input_field("Other Expenses", "settings-other-exp", exp.get("other", 0), "14%"),
            ]),
        ], className="card", style={"padding": "20px", "marginBottom": "16px"}),

        # ── Section 3: Net Worth Overrides ──
        html.Div([
            html.H5("Net Worth Overrides"),
            html.P("Assets and liabilities not tracked in your brokerage portfolio.",
                   style={"color": "var(--text-muted)", "fontSize": "0.85rem", "marginBottom": "12px"}),
            html.Div([
                _input_field("Real Estate Value", "settings-real-estate", nw.get("real_estate", 0)),
                _input_field("Cash & Savings", "settings-cash", nw.get("cash", 0)),
                _input_field("Pension / 2nd Pillar", "settings-pension", nw.get("pension", 0)),
                _input_field("Other Assets", "settings-other-assets", nw.get("other", 0)),
                _input_field("Liabilities (Debt)", "settings-liabilities", nw.get("liabilities", 0)),
            ]),
        ], className="card", style={"padding": "20px", "marginBottom": "16px"}),
    ])


def register_callbacks(app):
    # All income input IDs
    income_ids = ["settings-salary", "settings-side", "settings-dividends", "settings-other-inc"]
    # All expense input IDs
    expense_ids = [
        "settings-rent", "settings-utilities", "settings-insurance",
        "settings-gebaeude", "settings-hausneben", "settings-serafe",
        "settings-phone", "settings-claude", "settings-spotify",
        "settings-food", "settings-transport", "settings-entertainment",
        "settings-leibrente", "settings-taxes", "settings-other-exp",
    ]
    # Net worth input IDs
    nw_ids = ["settings-real-estate", "settings-cash", "settings-pension",
              "settings-other-assets", "settings-liabilities"]

    all_ids = income_ids + expense_ids + nw_ids

    @app.callback(
        Output("settings-save-feedback", "children"),
        Input("settings-save-btn", "n_clicks"),
        [State(id_, "value") for id_ in all_ids],
        prevent_initial_call=True,
    )
    def save_settings(n_clicks, salary, side, dividends, other_inc,
                      rent, utilities, insurance, gebaeude, hausneben, serafe,
                      phone, claude, spotify, food, transport, entertainment,
                      leibrente, taxes, other_exp,
                      real_estate, cash, pension, other_assets, liabilities):
        from datetime import datetime

        user_settings.save({
            "budget": {
                "income": {
                    "salary": salary or 0, "side": side or 0,
                    "dividends": dividends or 0, "other": other_inc or 0,
                },
                "expenses": {
                    "rent": rent or 0, "utilities": utilities or 0,
                    "insurance": insurance or 0, "gebaeude": gebaeude or 0,
                    "hausneben": hausneben or 0, "serafe": serafe or 0,
                    "phone": phone or 0, "claude": claude or 0,
                    "spotify": spotify or 0, "food": food or 0,
                    "transport": transport or 0, "entertainment": entertainment or 0,
                    "leibrente": leibrente or 0, "taxes": taxes or 0,
                    "other": other_exp or 0,
                },
            },
            "networth": {
                "real_estate": real_estate or 0, "cash": cash or 0,
                "pension": pension or 0, "other": other_assets or 0,
                "liabilities": liabilities or 0,
            },
        })

        return f"✓ Saved at {datetime.now().strftime('%H:%M:%S')}"
