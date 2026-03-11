# dataLoadMacro.py — Load, cache, and compute reference values for macro indicators
import logging
import pandas as pd
import numpy as np
from functools import lru_cache
from datetime import timedelta

import config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Core data loading
# ─────────────────────────────────────────────

@lru_cache(maxsize=1)
def load_macro_data() -> pd.DataFrame:
    """Load macro indicator data from CSV. Returns DataFrame with date index."""
    try:
        df = pd.read_csv("data/macro_data.csv", index_col="date", parse_dates=True)
        return df.sort_index()
    except FileNotFoundError:
        logger.warning("data/macro_data.csv not found — run fetchAPI.fetch_macro_data() first.")
        return pd.DataFrame()
    except Exception as e:
        logger.warning("Error loading macro data: %s", e)
        return pd.DataFrame()


def get_indicator(key: str, period: str = "1Y") -> pd.Series:
    """Return a time-filtered Series for one indicator key.

    period: '1M', '3M', '6M', '1Y', '5Y'
    """
    df = load_macro_data()
    if df.empty or key not in df.columns:
        return pd.Series(dtype=float)

    series = df[key].dropna()
    if series.empty:
        return series

    cutoff = _period_to_cutoff(series.index[-1], period)
    return series[series.index >= cutoff]


def get_reference_values(key: str) -> dict:
    """Compute reference statistics for an indicator over the trailing 52 weeks.

    Returns dict with: current, prev_close, day_change, day_change_pct,
    high_52w, low_52w, avg_52w, pct_from_high, yoy_change_pct
    """
    df = load_macro_data()
    if df.empty or key not in df.columns:
        return _empty_ref()

    series = df[key].dropna()
    if len(series) < 2:
        return _empty_ref()

    current = series.iloc[-1]
    prev_close = series.iloc[-2]
    day_change = current - prev_close
    day_change_pct = (day_change / prev_close * 100) if prev_close != 0 else 0

    # 52-week window
    one_year_ago = series.index[-1] - timedelta(days=365)
    trailing_52w = series[series.index >= one_year_ago]

    high_52w = trailing_52w.max() if not trailing_52w.empty else current
    low_52w = trailing_52w.min() if not trailing_52w.empty else current
    avg_52w = trailing_52w.mean() if not trailing_52w.empty else current
    pct_from_high = ((current - high_52w) / high_52w * 100) if high_52w != 0 else 0

    # Year-over-year change
    yoy_val = trailing_52w.iloc[0] if not trailing_52w.empty else current
    yoy_change_pct = ((current - yoy_val) / yoy_val * 100) if yoy_val != 0 else 0

    return {
        "current": round(current, 2),
        "prev_close": round(prev_close, 2),
        "day_change": round(day_change, 2),
        "day_change_pct": round(day_change_pct, 2),
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "avg_52w": round(avg_52w, 2),
        "pct_from_high": round(pct_from_high, 2),
        "yoy_change_pct": round(yoy_change_pct, 2),
    }


# ─────────────────────────────────────────────
# Derived indicators
# ─────────────────────────────────────────────

def get_yield_curve_spread(period: str = "1Y") -> pd.Series:
    """10Y minus 2Y Treasury yield spread. Negative = inverted (recession signal)."""
    df = load_macro_data()
    if df.empty:
        return pd.Series(dtype=float)

    us10y = df.get("us10y", pd.Series(dtype=float)).dropna()
    us2y = df.get("us2y", pd.Series(dtype=float)).dropna()

    if us10y.empty or us2y.empty:
        return pd.Series(dtype=float)

    spread = (us10y - us2y).dropna()
    if spread.empty:
        return spread

    cutoff = _period_to_cutoff(spread.index[-1], period)
    return spread[spread.index >= cutoff]


def get_ratio(key_a: str, key_b: str, period: str = "1Y") -> pd.Series:
    """Compute ratio of two indicators (e.g., gold/silver, HYG/TLT, EEM/SPY)."""
    df = load_macro_data()
    if df.empty:
        return pd.Series(dtype=float)

    a = df.get(key_a, pd.Series(dtype=float)).dropna()
    b = df.get(key_b, pd.Series(dtype=float)).dropna()

    if a.empty or b.empty:
        return pd.Series(dtype=float)

    ratio = (a / b.replace(0, np.nan)).dropna()
    if ratio.empty:
        return ratio

    cutoff = _period_to_cutoff(ratio.index[-1], period)
    return ratio[ratio.index >= cutoff]


def get_moving_average(key: str, window: int, period: str = "1Y") -> pd.Series:
    """Simple Moving Average for an indicator.

    Uses the full history to compute the MA, then filters to the requested
    period so that early values in the window are not NaN.
    """
    df = load_macro_data()
    if df.empty or key not in df.columns:
        return pd.Series(dtype=float)

    series = df[key].dropna()
    if series.empty or len(series) < window:
        return pd.Series(dtype=float)

    ma = series.rolling(window=window, min_periods=window).mean()
    ma = ma.dropna()
    if ma.empty:
        return ma

    cutoff = _period_to_cutoff(ma.index[-1], period)
    return ma[ma.index >= cutoff]


def get_ma_crossover_status(key: str, short: int = 50, long: int = 200) -> dict:
    """Return current MA alignment status for an indicator.

    Returns dict with: price, ma_short, ma_long, aligned (short > long),
    price_above_short, price_above_long, cross_signal.
    """
    df = load_macro_data()
    if df.empty or key not in df.columns:
        return _empty_ma_status()

    series = df[key].dropna()
    if len(series) < long:
        return _empty_ma_status()

    ma_s = series.rolling(window=short, min_periods=short).mean()
    ma_l = series.rolling(window=long, min_periods=long).mean()

    price = float(series.iloc[-1])
    ma_s_val = float(ma_s.iloc[-1]) if not np.isnan(ma_s.iloc[-1]) else 0
    ma_l_val = float(ma_l.iloc[-1]) if not np.isnan(ma_l.iloc[-1]) else 0

    if ma_s_val == 0 or ma_l_val == 0:
        return _empty_ma_status()

    aligned = ma_s_val > ma_l_val
    price_above_short = price > ma_s_val
    price_above_long = price > ma_l_val

    # Detect recent crossover (last 5 days)
    cross_signal = "none"
    if len(ma_s) >= 6 and len(ma_l) >= 6:
        prev_aligned = float(ma_s.iloc[-6]) > float(ma_l.iloc[-6])
        if aligned and not prev_aligned:
            cross_signal = "golden_cross"
        elif not aligned and prev_aligned:
            cross_signal = "death_cross"

    return {
        "price": round(price, 2),
        "ma_short": round(ma_s_val, 2),
        "ma_long": round(ma_l_val, 2),
        "aligned": aligned,
        "price_above_short": price_above_short,
        "price_above_long": price_above_long,
        "cross_signal": cross_signal,
    }


def get_vix_term_structure(period: str = "1Y") -> pd.Series:
    """VIX / VIX3M ratio series.

    < 1 = contango (normal, bullish for equities)
    > 1 = backwardation (fear spiking, bearish)
    """
    return get_ratio("vix", "vix3m", period)


def get_rate_of_change(key: str, periods: int = 20,
                       period_window: str = "1Y") -> pd.Series:
    """Percentage Rate of Change (ROC) over *periods* trading days.

    ROC = ((price - price_N_ago) / price_N_ago) * 100
    """
    df = load_macro_data()
    if df.empty or key not in df.columns:
        return pd.Series(dtype=float)

    series = df[key].dropna()
    if len(series) < periods + 1:
        return pd.Series(dtype=float)

    shifted = series.shift(periods)
    roc = ((series - shifted) / shifted.replace(0, np.nan) * 100).dropna()
    if roc.empty:
        return roc

    cutoff = _period_to_cutoff(roc.index[-1], period_window)
    return roc[roc.index >= cutoff]


def get_yield_slope_trend(lookback: int = 20, period: str = "1Y") -> dict:
    """Analyse the direction of yield-curve slope change.

    Returns dict with current_slope, slope_lookback_ago, slope_change,
    and trend ('steepening', 'flattening', 'stable').
    """
    spread = get_yield_curve_spread(period)
    if spread.empty or len(spread) < lookback + 1:
        return {"current_slope": 0, "slope_lookback_ago": 0,
                "slope_change": 0, "trend": "stable"}

    current_slope = float(spread.iloc[-1])
    lookback_slope = float(spread.iloc[-lookback - 1])
    slope_change = round(current_slope - lookback_slope, 4)

    if slope_change > 0.05:
        trend = "steepening"
    elif slope_change < -0.05:
        trend = "flattening"
    else:
        trend = "stable"

    return {
        "current_slope": round(current_slope, 4),
        "slope_lookback_ago": round(lookback_slope, 4),
        "slope_change": slope_change,
        "trend": trend,
    }


def get_yield_slope_momentum(period: str = "1Y") -> pd.Series:
    """Rolling 20-day change in yield-curve spread (for charting)."""
    spread = get_yield_curve_spread(period)
    if spread.empty or len(spread) < 21:
        return pd.Series(dtype=float)

    momentum = (spread - spread.shift(20)).dropna()
    return momentum


def get_drawdown_from_ath(key: str, period: str = "1Y") -> pd.Series:
    """Percentage drawdown from all-time high for an indicator."""
    df = load_macro_data()
    if df.empty or key not in df.columns:
        return pd.Series(dtype=float)

    series = df[key].dropna()
    if series.empty:
        return series

    running_max = series.cummax()
    drawdown = ((series - running_max) / running_max * 100).dropna()

    cutoff = _period_to_cutoff(drawdown.index[-1], period)
    return drawdown[drawdown.index >= cutoff]


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _period_to_cutoff(end_date, period: str):
    """Convert period string to a cutoff date."""
    mapping = {
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
        "6M": timedelta(days=182),
        "1Y": timedelta(days=365),
        "5Y": timedelta(days=1826),
    }
    delta = mapping.get(period, timedelta(days=365))
    return end_date - delta


def _empty_ma_status() -> dict:
    """Return an empty MA crossover status dict."""
    return {
        "price": 0, "ma_short": 0, "ma_long": 0,
        "aligned": False, "price_above_short": False,
        "price_above_long": False, "cross_signal": "none",
    }


def _empty_ref() -> dict:
    """Return an empty reference dict."""
    return {
        "current": 0, "prev_close": 0, "day_change": 0, "day_change_pct": 0,
        "high_52w": 0, "low_52w": 0, "avg_52w": 0, "pct_from_high": 0,
        "yoy_change_pct": 0,
    }


def threshold_color(key: str, value: float) -> str:
    """Return a color based on configured thresholds for an indicator."""
    import Styles
    thresholds = config.MACRO_THRESHOLDS.get(key)
    if not thresholds:
        return Styles.colorPalette[0]

    if value < thresholds["low"]:
        return Styles.strongGreen
    elif value < thresholds["mid"]:
        return Styles.colorPalette[1]
    elif value < thresholds["high"]:
        return Styles.colorPalette[3]
    else:
        return Styles.strongRed
