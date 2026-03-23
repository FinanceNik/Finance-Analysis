"""Consolidated Tools page — combines Watchlist, Sizing, What-If, Tax-Loss, Rebalancing, Alerts."""
import dash_bootstrap_components as dbc
from dash import html
from pages import (page_watchlist, page_sizing, page_whatif,
                   page_taxloss, page_rebalancing, page_alerts)


def layout():
    return html.Div([
        html.H4("Tools"),
        dbc.Tabs([
            dbc.Tab(page_watchlist.layout(), label="Watchlist", tab_id="tools-watchlist"),
            dbc.Tab(page_rebalancing.layout(), label="Rebalancing", tab_id="tools-rebalancing"),
            dbc.Tab(page_sizing.layout(), label="Position Sizing", tab_id="tools-sizing"),
            dbc.Tab(page_whatif.layout(), label="What-If", tab_id="tools-whatif"),
            dbc.Tab(page_taxloss.layout(), label="Tax-Loss", tab_id="tools-taxloss"),
            dbc.Tab(page_alerts.layout(), label="Alerts", tab_id="tools-alerts"),
        ], id="tools-tabs", active_tab="tools-watchlist"),
    ])


def register_callbacks(app):
    # Individual page callbacks are already registered in GUI.py
    pass
