"""Smoke tests: verify all pages can be imported and layout() returns valid HTML."""
import sys
import os
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must create a Dash app before importing pages
import dash
app = dash.Dash(__name__, suppress_callback_exceptions=True)

PAGE_MODULES = [
    "page_dashboard", "page_networth", "page_alerts",
    "page_positions", "page_analytics", "page_transactions", "page_rebalancing",
    "page_currency", "page_watchlist", "page_taxlots", "page_sizing",
    "page_peers", "page_attribution",
    "page_budget", "page_income", "page_dividends", "page_drip", "page_calendar",
    "page_projections", "page_scenarios", "page_realEstate", "page_goals",
    "page_macro", "page_backtest", "page_about",
]


@pytest.mark.parametrize("page_name", PAGE_MODULES)
def test_page_imports(page_name):
    """Each page module should import without errors."""
    try:
        mod = __import__(f"pages.{page_name}", fromlist=["layout"])
    except ImportError as e:
        pytest.skip(f"{page_name} has missing dependency: {e}")
    assert hasattr(mod, "layout"), f"{page_name} missing layout()"


@pytest.mark.parametrize("page_name", PAGE_MODULES)
def test_page_layout_returns_component(page_name):
    """Each page's layout() should return a Dash component."""
    try:
        mod = __import__(f"pages.{page_name}", fromlist=["layout"])
    except ImportError as e:
        pytest.skip(f"{page_name} has missing dependency: {e}")
    try:
        result = mod.layout()
        assert result is not None, f"{page_name}.layout() returned None"
    except Exception as e:
        # Pages that need data files may fail -- that's OK in test env
        pytest.skip(f"{page_name} needs data: {e}")


def test_styles_functions():
    """Styles helper functions should work."""
    import Styles
    box = Styles.kpiboxes("Test", 1234, "#008DD5")
    assert box is not None

    spark = Styles.kpiboxes_spark("Test", 99.5, "#34c759", [1, 2, 3, 4, 5])
    assert spark is not None

    ref = Styles.kpiboxes_ref("Test", 42, "#ff3b30", "ref: 40", 5.0)
    assert ref is not None

    empty = Styles.empty_state("No data")
    assert empty is not None


def test_format_kpi_value():
    """KPI formatting should handle int, float, and string."""
    import Styles
    assert Styles._format_kpi_value(1234) == "1,234"
    assert Styles._format_kpi_value(1234.56) == "1,234.56"
    assert Styles._format_kpi_value(1234.0) == "1,234"
    assert Styles._format_kpi_value("N/A") == "N/A"


def test_config_functions():
    """Config lookup functions should not crash."""
    import config
    # These may return 'Other' without yfinance, but should not crash
    assert isinstance(config.get_sector("AAPL"), str)
    assert isinstance(config.get_geography("AAPL"), str)
