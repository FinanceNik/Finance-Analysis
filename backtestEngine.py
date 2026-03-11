# backtestEngine.py — Signal-driven backtesting engine
#
# Long-only strategy across ETFs, bonds, and commodities.
# Monthly rebalancing based on macro signal scores.
# Self-contained: reimplements point-in-time (PIT) data helpers
# so that dataLoadMacro.py and macroSignal.py are not modified.

import numpy as np
import pandas as pd
from datetime import timedelta

import config

# Import pure scoring primitives (no data dependency)
from macroSignal import (
    score_threshold, score_yield_spread, score_trend, score_ratio,
    score_ma_crossover, score_vix_term_structure, score_roc,
    score_slope_change, _clamp, _section_result, _action_for_score,
)


# ─────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────

_CACHE = {}


def load_and_prepare() -> pd.DataFrame:
    """Load macro_data.csv, drop unusable columns, forward-fill NaN."""
    if "df" in _CACHE:
        return _CACHE["df"]

    try:
        df = pd.read_csv("data/macro_data.csv", index_col="date", parse_dates=True)
    except FileNotFoundError:
        return pd.DataFrame()

    df = df.sort_index()
    # Drop columns with no data or excluded assets
    for col in ["put_call", "btc", "eth"]:
        if col in df.columns:
            df = df.drop(columns=[col])
    df = df.ffill()
    _CACHE["df"] = df
    return df


def clear_cache():
    """Clear the module-level cache (e.g. after data refresh)."""
    _CACHE.clear()


# ─────────────────────────────────────────────
# Point-in-time data helpers
# ─────────────────────────────────────────────

def _empty_ref() -> dict:
    return {
        "current": 0, "prev_close": 0, "day_change": 0, "day_change_pct": 0,
        "high_52w": 0, "low_52w": 0, "avg_52w": 0, "pct_from_high": 0,
        "yoy_change_pct": 0,
    }


def _pit_reference_values(series: pd.Series) -> dict:
    """Point-in-time equivalent of dataLoadMacro.get_reference_values().

    series must already be truncated to as_of_date and NaN-dropped.
    """
    if len(series) < 2:
        return _empty_ref()

    current = float(series.iloc[-1])
    prev_close = float(series.iloc[-2])
    day_change = current - prev_close
    day_change_pct = (day_change / prev_close * 100) if prev_close != 0 else 0

    one_year_ago = series.index[-1] - timedelta(days=365)
    trailing = series[series.index >= one_year_ago]

    high_52w = float(trailing.max()) if not trailing.empty else current
    low_52w = float(trailing.min()) if not trailing.empty else current
    avg_52w = float(trailing.mean()) if not trailing.empty else current
    pct_from_high = ((current - high_52w) / high_52w * 100) if high_52w != 0 else 0

    yoy_val = float(trailing.iloc[0]) if not trailing.empty else current
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


def _pit_ratio(df_pit: pd.DataFrame, key_a: str, key_b: str) -> tuple:
    """Return (current_ratio, avg_ratio) for two columns in truncated df.

    Returns (0, 0) if data is insufficient.
    """
    if key_a not in df_pit.columns or key_b not in df_pit.columns:
        return 0.0, 0.0

    a = df_pit[key_a].dropna()
    b = df_pit[key_b].dropna()
    if a.empty or b.empty:
        return 0.0, 0.0

    ratio = (a / b.replace(0, np.nan)).dropna()
    if ratio.empty:
        return 0.0, 0.0

    # Trailing 1Y
    one_year_ago = ratio.index[-1] - timedelta(days=365)
    trailing = ratio[ratio.index >= one_year_ago]
    if trailing.empty:
        return 0.0, 0.0

    return float(trailing.iloc[-1]), float(trailing.mean())


def _pit_yield_spread(df_pit: pd.DataFrame) -> float:
    """10Y minus 2Y spread at the latest point in truncated df."""
    if "us10y" not in df_pit.columns or "us2y" not in df_pit.columns:
        return 0.0
    us10y = df_pit["us10y"].dropna()
    us2y = df_pit["us2y"].dropna()
    if us10y.empty or us2y.empty:
        return 0.0
    spread = (us10y - us2y).dropna()
    return float(spread.iloc[-1]) if not spread.empty else 0.0


def _pit_ma_crossover(df_pit: pd.DataFrame, key: str,
                       short: int = 50, long: int = 200) -> dict:
    """Point-in-time MA crossover status."""
    empty = {
        "price": 0, "ma_short": 0, "ma_long": 0,
        "aligned": False, "price_above_short": False,
        "price_above_long": False, "cross_signal": "none",
    }
    if key not in df_pit.columns:
        return empty

    series = df_pit[key].dropna()
    if len(series) < long:
        return empty

    ma_s = series.rolling(window=short, min_periods=short).mean()
    ma_l = series.rolling(window=long, min_periods=long).mean()

    price = float(series.iloc[-1])
    ma_s_val = float(ma_s.iloc[-1]) if not np.isnan(ma_s.iloc[-1]) else 0
    ma_l_val = float(ma_l.iloc[-1]) if not np.isnan(ma_l.iloc[-1]) else 0

    if ma_s_val == 0 or ma_l_val == 0:
        return empty

    aligned = ma_s_val > ma_l_val
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
        "price_above_short": price > ma_s_val,
        "price_above_long": price > ma_l_val,
        "cross_signal": cross_signal,
    }


def _pit_vix_term(df_pit: pd.DataFrame) -> float:
    """VIX / VIX3M ratio at latest point."""
    if "vix" not in df_pit.columns or "vix3m" not in df_pit.columns:
        return 0.0
    vix = df_pit["vix"].dropna()
    vix3m = df_pit["vix3m"].dropna()
    if vix.empty or vix3m.empty:
        return 0.0
    ratio = (vix / vix3m.replace(0, np.nan)).dropna()
    return float(ratio.iloc[-1]) if not ratio.empty else 0.0


def _pit_roc(df_pit: pd.DataFrame, key: str, periods: int = 20) -> float:
    """Rate of Change at latest point."""
    if key not in df_pit.columns:
        return 0.0
    series = df_pit[key].dropna()
    if len(series) < periods + 1:
        return 0.0
    current = float(series.iloc[-1])
    past = float(series.iloc[-periods - 1])
    if past == 0:
        return 0.0
    return (current - past) / past * 100


def _pit_yield_slope(df_pit: pd.DataFrame, lookback: int = 20) -> dict:
    """Yield curve slope direction over lookback period."""
    if "us10y" not in df_pit.columns or "us2y" not in df_pit.columns:
        return {"current_slope": 0, "slope_change": 0, "trend": "stable"}

    us10y = df_pit["us10y"].dropna()
    us2y = df_pit["us2y"].dropna()
    spread = (us10y - us2y).dropna()

    if spread.empty or len(spread) < lookback + 1:
        return {"current_slope": 0, "slope_change": 0, "trend": "stable"}

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
        "slope_change": slope_change,
        "trend": trend,
    }


# ─────────────────────────────────────────────
# Point-in-time section scorers
# ─────────────────────────────────────────────

def pit_score_sentiment(df_pit: pd.DataFrame) -> dict:
    """Sentiment: VIX + HYG/TLT ratio (skip put_call — no data)."""
    components = []

    if "vix" in df_pit.columns:
        ref = _pit_reference_values(df_pit["vix"].dropna())
        if ref["current"] != 0:
            s = score_threshold(ref["current"], low=15, mid=25, high=35)
            components.append(("VIX", s))

    cur, avg = _pit_ratio(df_pit, "hyg", "tlt")
    if cur != 0 and avg != 0:
        s = score_ratio(cur, avg, above_is_bullish=True)
        components.append(("HYG/TLT", s))

    return _section_result("Sentiment", components)


def pit_score_rates(df_pit: pd.DataFrame) -> dict:
    """Rates: yield spread + DXY + 10Y trend."""
    components = []

    spread_val = _pit_yield_spread(df_pit)
    if spread_val != 0 or True:  # spread can legitimately be 0
        s = score_yield_spread(spread_val)
        components.append(("Yield Curve", s))

    if "dxy" in df_pit.columns:
        ref = _pit_reference_values(df_pit["dxy"].dropna())
        if ref["current"] != 0:
            s = score_threshold(ref["current"], low=95, mid=100, high=105,
                                invert=True)
            components.append(("Dollar (DXY)", s))

    if "us10y" in df_pit.columns:
        ref = _pit_reference_values(df_pit["us10y"].dropna())
        if ref["current"] != 0:
            s = score_trend(ref, invert=True)
            components.append(("10Y Yield", s))

    return _section_result("Rates", components)


def pit_score_equities(df_pit: pd.DataFrame) -> dict:
    """Equities: S&P 500, MSCI World, EM, EM/US ratio."""
    components = []

    for key, label in [("sp500", "S&P 500"), ("msci_world", "MSCI World"),
                        ("em", "Emerging Mkts")]:
        if key in df_pit.columns:
            ref = _pit_reference_values(df_pit[key].dropna())
            if ref["current"] != 0:
                s = score_trend(ref)
                components.append((label, s))

    cur, avg = _pit_ratio(df_pit, "em", "spy")
    if cur != 0 and avg != 0:
        s = score_ratio(cur, avg, above_is_bullish=True)
        components.append(("EM/US Ratio", s))

    return _section_result("Equities", components)


def pit_score_commodities(df_pit: pd.DataFrame) -> dict:
    """Commodities: Gold, Silver, Gold/Silver ratio, Oil."""
    components = []

    if "gold" in df_pit.columns:
        ref = _pit_reference_values(df_pit["gold"].dropna())
        if ref["current"] != 0:
            s = score_trend(ref)
            components.append(("Gold", s))

    if "silver" in df_pit.columns:
        ref = _pit_reference_values(df_pit["silver"].dropna())
        if ref["current"] != 0:
            s = score_trend(ref)
            components.append(("Silver", s))

    cur, avg = _pit_ratio(df_pit, "gold", "silver")
    if cur != 0 and avg != 0:
        s = score_ratio(cur, avg, above_is_bullish=False)
        components.append(("Gold/Silver", s))

    if "oil" in df_pit.columns:
        ref = _pit_reference_values(df_pit["oil"].dropna())
        if ref["current"] != 0:
            s = score_trend(ref, invert=True)
            components.append(("Crude Oil", s))

    return _section_result("Commodities", components)


def pit_score_predictive(df_pit: pd.DataFrame) -> dict:
    """Predictive: DMA crossover, VIX term, ROC, Cu/Au, Yield slope."""
    components = []

    # 1. Moving Average Crossovers — average across SPY, MSCI, EM
    ma_scores = []
    for key in ["spy", "msci_world", "em"]:
        status = _pit_ma_crossover(df_pit, key, short=50, long=200)
        if status["price"] != 0:
            ma_scores.append(score_ma_crossover(status))
    if ma_scores:
        avg_ma = round(float(np.mean(ma_scores)), 1)
        components.append(("50/200 DMA", avg_ma))

    # 2. VIX Term Structure
    ratio_val = _pit_vix_term(df_pit)
    if ratio_val > 0:
        s = score_vix_term_structure(ratio_val)
        components.append(("VIX Term Struct.", s))

    # 3. Rate of Change — S&P 500 (20-day)
    roc_val = _pit_roc(df_pit, "sp500", periods=20)
    if roc_val != 0 or True:  # ROC can legitimately be 0
        s = score_roc(roc_val)
        components.append(("Momentum (ROC)", s))

    # 4. Copper/Gold Ratio
    cur, avg = _pit_ratio(df_pit, "copper", "gold")
    if cur != 0 and avg != 0:
        s = score_ratio(cur, avg, above_is_bullish=True)
        components.append(("Copper/Gold", s))

    # 5. Yield Curve Slope Trend
    slope = _pit_yield_slope(df_pit, lookback=20)
    if slope["current_slope"] != 0 or slope["slope_change"] != 0:
        s = score_slope_change(slope["slope_change"])
        components.append(("Yield Slope Trend", s))

    return _section_result("Predictive", components)


# ─────────────────────────────────────────────
# Signal aggregation
# ─────────────────────────────────────────────

def compute_signal_at_date(df_full: pd.DataFrame,
                           as_of_date) -> dict:
    """Compute the full composite signal as of a specific date.

    Returns:
        {"score": float, "sections": {name: score}, "action": str, "color": str}
    """
    df_pit = df_full.loc[:as_of_date]

    section_fns = {
        "sentiment":   pit_score_sentiment,
        "rates":       pit_score_rates,
        "equities":    pit_score_equities,
        "commodities": pit_score_commodities,
        "predictive":  pit_score_predictive,
    }

    weights = config.BACKTEST_SIGNAL_WEIGHTS

    sections = {}
    weighted_sum = 0.0
    total_weight = 0.0
    for key, fn in section_fns.items():
        result = fn(df_pit)
        sections[key] = result["score"]
        w = weights.get(key, 0.20)
        weighted_sum += result["score"] * w
        total_weight += w

    overall = round(weighted_sum / total_weight, 1) if total_weight else 0.0
    action, color = _action_for_score(overall)

    return {
        "score": overall,
        "sections": sections,
        "action": action,
        "color": color,
    }


# ─────────────────────────────────────────────
# Allocation model
# ─────────────────────────────────────────────

def compute_allocation(signal: dict, sensitivity: float = 1.0) -> dict:
    """Translate signal scores into long-only portfolio weights.

    sensitivity: how aggressively signals tilt from base allocation.
        0.0 = always base allocation; 2.0 = double tilt.
    """
    scores = signal["sections"]
    base = config.BACKTEST_BASE_ALLOCATION
    assets = config.BACKTEST_ASSETS

    # Compute tilt factors (each in [-1, +1], scaled by sensitivity)
    eq_score = scores.get("equities", 0)
    pred_score = scores.get("predictive", 0)
    equity_tilt = (eq_score * 0.6 + pred_score * 0.4) / 100 * sensitivity

    rate_score = scores.get("rates", 0)
    bond_tilt = -rate_score / 100 * sensitivity * 0.5

    comm_score = scores.get("commodities", 0)
    commodity_tilt = comm_score / 100 * sensitivity

    # Sentiment risk scaling: extreme fear → reduce total exposure to 50%
    sent_score = scores.get("sentiment", 0)
    risk_scale = 1.0 + sent_score / 200   # range 0.5 .. 1.5
    risk_scale = max(0.5, min(1.5, risk_scale))

    weights = {}
    for asset, base_w in base.items():
        asset_class = assets[asset]["class"]
        if asset_class == "equity":
            tilt = equity_tilt
        elif asset_class == "bond":
            tilt = bond_tilt
        elif asset_class == "commodity":
            tilt = commodity_tilt
        else:
            tilt = 0

        raw_w = base_w * (1 + tilt) * risk_scale
        weights[asset] = max(0.0, raw_w)   # long-only constraint

    # Normalize if total > 1.0 (remainder = cash)
    total = sum(weights.values())
    if total > 1.0:
        for k in weights:
            weights[k] /= total

    return weights


# ─────────────────────────────────────────────
# Backtesting loop
# ─────────────────────────────────────────────

def run_backtest(df_full: pd.DataFrame = None,
                 sensitivity: float = 1.0) -> pd.DataFrame:
    """Run the signal-driven backtest with monthly rebalancing.

    Returns DataFrame indexed by date with columns:
        portfolio, spy, urth, signal_score, w_{asset}...
    """
    if df_full is None:
        df_full = load_and_prepare()
    if df_full.empty:
        return pd.DataFrame()

    warmup = config.BACKTEST_MA_WARMUP
    if len(df_full) <= warmup:
        return pd.DataFrame()

    dates = df_full.index[warmup:]
    assets = config.BACKTEST_ASSETS

    # Identify month-end rebalancing dates
    date_series = pd.Series(dates, index=dates)
    rebal_dates = set(date_series.groupby(pd.Grouper(freq="ME")).last().values)

    portfolio_value = 100.0
    spy_value = 100.0
    urth_value = 100.0

    current_weights = {}
    signal_score = 0.0
    prev_prices = None
    records = []

    for date in dates:
        # Current prices for all assets
        prices = {}
        for asset in assets:
            if asset in df_full.columns:
                prices[asset] = float(df_full.at[date, asset])
            else:
                prices[asset] = 0.0

        # Rebalance on month-end or first iteration
        if date in rebal_dates or not current_weights:
            signal = compute_signal_at_date(df_full, date)
            current_weights = compute_allocation(signal, sensitivity)
            signal_score = signal["score"]

        # Compute daily returns
        if prev_prices is not None:
            daily_return = 0.0
            for asset, w in current_weights.items():
                if w > 0 and prev_prices.get(asset, 0) > 0:
                    asset_ret = (prices[asset] - prev_prices[asset]) / prev_prices[asset]
                    daily_return += w * asset_ret

            portfolio_value *= (1 + daily_return)

            # Benchmark returns
            spy_prev = prev_prices.get("spy", 0)
            if spy_prev > 0:
                spy_value *= (1 + (prices.get("spy", 0) - spy_prev) / spy_prev)

            urth_prev = prev_prices.get("msci_world", 0)
            if urth_prev > 0:
                urth_value *= (1 + (prices.get("msci_world", 0) - urth_prev) / urth_prev)

        records.append({
            "date": date,
            "portfolio": round(portfolio_value, 4),
            "spy": round(spy_value, 4),
            "urth": round(urth_value, 4),
            "signal_score": signal_score if (date in rebal_dates or len(records) == 0) else np.nan,
            **{f"w_{k}": round(current_weights.get(k, 0), 4) for k in assets},
        })

        prev_prices = prices

    result = pd.DataFrame(records).set_index("date")
    return result


# ─────────────────────────────────────────────
# Performance metrics
# ─────────────────────────────────────────────

def compute_metrics(result_df: pd.DataFrame,
                    rf: float = None) -> dict:
    """Compute CAGR, Sharpe, Sortino, Max Drawdown, Alpha vs SPY/URTH."""
    if rf is None:
        rf = config.RISK_FREE_RATE

    if result_df.empty or len(result_df) < 2:
        return {k: 0.0 for k in [
            "cagr", "sharpe", "sortino", "max_drawdown",
            "alpha_spy", "alpha_urth", "annual_vol",
            "spy_cagr", "urth_cagr", "total_return",
        ]}

    daily_returns = result_df["portfolio"].pct_change().dropna()
    total_days = (result_df.index[-1] - result_df.index[0]).days
    if total_days <= 0:
        total_days = 1

    # Total return
    total_return = result_df["portfolio"].iloc[-1] / result_df["portfolio"].iloc[0] - 1

    # CAGR
    cagr = (1 + total_return) ** (365.25 / total_days) - 1

    # Sharpe
    annual_ret = float(daily_returns.mean()) * 252
    annual_vol = float(daily_returns.std()) * np.sqrt(252)
    sharpe = (annual_ret - rf) / annual_vol if annual_vol > 0 else 0

    # Sortino
    neg = daily_returns[daily_returns < 0]
    downside_vol = float(neg.std()) * np.sqrt(252) if len(neg) > 1 else 0
    sortino = (annual_ret - rf) / downside_vol if downside_vol > 0 else 0

    # Max Drawdown
    cummax = result_df["portfolio"].cummax()
    drawdown = (result_df["portfolio"] - cummax) / cummax
    max_dd = float(drawdown.min())

    # Benchmark CAGRs + Alpha
    spy_total = result_df["spy"].iloc[-1] / result_df["spy"].iloc[0] - 1
    spy_cagr = (1 + spy_total) ** (365.25 / total_days) - 1

    urth_total = result_df["urth"].iloc[-1] / result_df["urth"].iloc[0] - 1
    urth_cagr = (1 + urth_total) ** (365.25 / total_days) - 1

    return {
        "cagr": round(cagr, 4),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "max_drawdown": round(max_dd, 4),
        "alpha_spy": round(cagr - spy_cagr, 4),
        "alpha_urth": round(cagr - urth_cagr, 4),
        "annual_vol": round(annual_vol, 4),
        "spy_cagr": round(spy_cagr, 4),
        "urth_cagr": round(urth_cagr, 4),
        "total_return": round(total_return, 4),
    }


# ─────────────────────────────────────────────
# Alpha optimization (grid search)
# ─────────────────────────────────────────────

def optimize_alpha(df_full: pd.DataFrame = None,
                   target: str = "alpha_spy") -> dict:
    """Grid search over sensitivity to maximise the target metric.

    Returns:
        {
            "optimal_sensitivity": float,
            "optimal_metrics": dict,
            "all_results": [(sensitivity, metrics), ...],
            "optimal_backtest": pd.DataFrame,
        }
    """
    if df_full is None:
        df_full = load_and_prepare()
    if df_full.empty:
        return {"optimal_sensitivity": 0, "optimal_metrics": {},
                "all_results": [], "optimal_backtest": pd.DataFrame()}

    lo, hi = config.BACKTEST_SENSITIVITY_RANGE
    steps = config.BACKTEST_SENSITIVITY_STEPS
    sensitivities = np.linspace(lo, hi, steps)

    best_val = -np.inf
    best_s = 0.0
    best_m = {}
    best_df = pd.DataFrame()
    results = []

    for s in sensitivities:
        s = round(float(s), 2)
        bt = run_backtest(df_full, sensitivity=s)
        if bt.empty:
            continue
        m = compute_metrics(bt)
        results.append((s, m))
        if m.get(target, -np.inf) > best_val:
            best_val = m[target]
            best_s = s
            best_m = m
            best_df = bt

    return {
        "optimal_sensitivity": best_s,
        "optimal_metrics": best_m,
        "all_results": results,
        "optimal_backtest": best_df,
    }
