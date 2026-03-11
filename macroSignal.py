# macroSignal.py — Macro Signal Scoring Engine
#
# Synthesises individual macro indicators into per-section and overall
# buy / hold / sell signals.  All scores are on a −100 (bearish) to
# +100 (bullish) scale.  Zero means neutral.
#
# This module contains pure scoring logic; it reads data through
# dataLoadMacro but has NO Dash/HTML dependency.

import numpy as np
import config
import dataLoadMacro as dlm


# ─────────────────────────────────────────────
# Low-level scoring primitives
# ─────────────────────────────────────────────

def _clamp(value: float, lo: float = -100, hi: float = 100) -> float:
    return max(lo, min(hi, value))


def score_threshold(value: float, low: float, mid: float, high: float,
                    invert: bool = False) -> float:
    """Score an indicator that has well-known threshold bands.

    When *invert* is True a **low** reading is bearish (e.g. equity PE
    below average is cheap = bullish → invert=False).  For indicators
    like VIX where low = calm = bullish, invert=False too.

    Piecewise linear mapping:
        value <= low    → +100
        value == mid    →    0
        value >= high   → −100
    """
    if value <= low:
        score = 100.0
    elif value <= mid:
        score = 100.0 * (mid - value) / (mid - low) if mid != low else 0
    elif value <= high:
        score = -100.0 * (value - mid) / (high - mid) if high != mid else 0
    else:
        score = -100.0

    if invert:
        score = -score
    return _clamp(round(score, 1))


def score_yield_spread(spread_value: float) -> float:
    """Score the 10Y−2Y yield-curve spread.

    >1.5 → +100, 0→0, <−0.5 → −100, linear between.
    """
    if spread_value >= 1.5:
        return 100.0
    if spread_value >= 0:
        return _clamp(round(spread_value / 1.5 * 100, 1))
    if spread_value >= -0.5:
        return _clamp(round(spread_value / 0.5 * -100 * -1, 1))
    return -100.0


def score_trend(ref: dict, invert: bool = False) -> float:
    """Score a trend-following indicator using 52-week position + YoY momentum.

    ref is the dict returned by dataLoadMacro.get_reference_values().
    """
    current = ref["current"]
    high = ref["high_52w"]
    low = ref["low_52w"]
    yoy = ref["yoy_change_pct"]

    # Position score: where in the 52w range (0 at low, 100 at high)
    rng = high - low
    if rng > 0:
        position = (current - low) / rng  # 0..1
        position_score = (position - 0.5) * 200  # −100..+100
    else:
        position_score = 0.0

    # Momentum score: YoY change capped at ±50 → maps to ±100
    momentum_score = _clamp(yoy * 2, -100, 100)

    score = 0.5 * position_score + 0.5 * momentum_score
    if invert:
        score = -score
    return _clamp(round(score, 1))


def score_ratio(current: float, avg: float,
                above_is_bullish: bool = True) -> float:
    """Score a ratio indicator by comparing current to its average.

    Deviation capped at ±30 % → maps to ±100.
    """
    if avg == 0:
        return 0.0
    pct_dev = (current - avg) / avg * 100  # e.g. +12 means 12 % above avg
    score = _clamp(pct_dev / 30 * 100, -100, 100)
    if not above_is_bullish:
        score = -score
    return _clamp(round(score, 1))


# ─────────────────────────────────────────────
# Predictive scoring primitives
# ─────────────────────────────────────────────

def score_ma_crossover(status: dict) -> float:
    """Score a moving-average crossover status dict.

    Price above both MAs + short above long → +100 (strong uptrend).
    Golden cross (recent crossover) → +50.
    Death cross → −50.
    Price below both MAs → −100.
    """
    if status["price"] == 0:
        return 0.0

    aligned = status["aligned"]           # short MA > long MA
    above_short = status["price_above_short"]
    above_long = status["price_above_long"]
    cross = status["cross_signal"]

    if above_short and above_long and aligned:
        return 100.0   # strong uptrend
    if cross == "golden_cross":
        return 50.0
    if above_long and aligned:
        return 60.0    # above long MA, MAs aligned bullish
    if above_long and not aligned:
        return 20.0    # above long MA but short crossing down
    if cross == "death_cross":
        return -50.0
    if not above_short and not above_long and not aligned:
        return -100.0  # strong downtrend
    if not above_long and not aligned:
        return -60.0
    # Mixed / transitional
    return 0.0


def score_vix_term_structure(ratio: float) -> float:
    """Score VIX/VIX3M ratio.

    ratio < 0.85 → +100 (deep contango, calm)
    ratio = 1.0  → 0    (neutral)
    ratio > 1.15 → −100 (deep backwardation, panic)
    """
    if ratio <= 0:
        return 0.0
    # Linear: 0.85 → +100, 1.0 → 0, 1.15 → −100
    if ratio <= 1.0:
        score = (1.0 - ratio) / 0.15 * 100
    else:
        score = -(ratio - 1.0) / 0.15 * 100
    return _clamp(round(score, 1))


def score_roc(roc_pct: float) -> float:
    """Score a Rate of Change value.

    ±10 % → ±100 linearly.
    """
    return _clamp(round(roc_pct / 10 * 100, 1))


def score_slope_change(slope_change: float) -> float:
    """Score the direction of yield-curve slope change.

    +0.5 pp change → +100 (steepening = bullish)
    −0.5 pp change → −100 (flattening = bearish)
    """
    return _clamp(round(slope_change / 0.5 * 100, 1))


# ─────────────────────────────────────────────
# Section scorers
# ─────────────────────────────────────────────
# Each returns:
#   {
#     "name":       str,          # section display name
#     "score":      float,        # −100..+100
#     "action":     str,          # "BUY" / "HOLD" / etc.
#     "color":      str,          # hex color for action badge
#     "components": [(name, score), ...]
#   }

def _action_for_score(score: float) -> tuple:
    """Return (action_text, color) for a given score."""
    for threshold, action, color in config.SIGNAL_ACTIONS:
        if score >= threshold:
            return action, color
    # Fallback (shouldn't happen)
    return "SELL", "#ff3b30"


def _section_result(name: str, components: list) -> dict:
    scores = [s for _, s in components]
    avg = round(float(np.mean(scores)), 1) if scores else 0.0
    action, color = _action_for_score(avg)
    return {
        "name": name,
        "score": avg,
        "action": action,
        "color": color,
        "components": components,
    }


def score_sentiment() -> dict:
    """Market Sentiment: VIX, Put/Call, HYG/TLT ratio."""
    components = []

    # VIX — low is bullish
    ref = dlm.get_reference_values("vix")
    if ref["current"] != 0:
        s = score_threshold(ref["current"], low=15, mid=25, high=35)
        components.append(("VIX", s))

    # Put/Call — low is bullish
    ref = dlm.get_reference_values("put_call")
    if ref["current"] != 0:
        s = score_threshold(ref["current"], low=0.7, mid=1.0, high=1.3)
        components.append(("Put/Call", s))

    # HYG/TLT ratio — rising is bullish (risk appetite)
    ratio = dlm.get_ratio("hyg", "tlt", period="1Y")
    if not ratio.empty:
        current = float(ratio.iloc[-1])
        avg = float(ratio.mean())
        s = score_ratio(current, avg, above_is_bullish=True)
        components.append(("HYG/TLT", s))

    return _section_result("Sentiment", components)


def score_rates() -> dict:
    """Rates & Yields: yield-curve spread, DXY, 10Y trend."""
    components = []

    # Yield curve spread
    spread = dlm.get_yield_curve_spread(period="1Y")
    if not spread.empty:
        s = score_yield_spread(float(spread.iloc[-1]))
        components.append(("Yield Curve", s))

    # DXY — strong dollar hurts equities/commodities, so invert
    ref = dlm.get_reference_values("dxy")
    if ref["current"] != 0:
        s = score_threshold(ref["current"], low=95, mid=100, high=105,
                            invert=True)
        components.append(("Dollar (DXY)", s))

    # 10Y yield trend — rising yields = tighter conditions = mildly bearish
    ref = dlm.get_reference_values("us10y")
    if ref["current"] != 0:
        s = score_trend(ref, invert=True)
        components.append(("10Y Yield", s))

    return _section_result("Rates", components)


def score_equities() -> dict:
    """Equity Markets: S&P 500, MSCI World, EM, EM/US ratio."""
    components = []

    for key, label in [("sp500", "S&P 500"), ("msci_world", "MSCI World"),
                        ("em", "Emerging Mkts")]:
        ref = dlm.get_reference_values(key)
        if ref["current"] != 0:
            s = score_trend(ref)
            components.append((label, s))

    # EM/US ratio — rising = EM outperformance (neutral signal for overall)
    ratio = dlm.get_ratio("em", "spy", period="1Y")
    if not ratio.empty:
        current = float(ratio.iloc[-1])
        avg = float(ratio.mean())
        s = score_ratio(current, avg, above_is_bullish=True)
        components.append(("EM/US Ratio", s))

    return _section_result("Equities", components)


def score_commodities() -> dict:
    """Commodities: Gold, Silver, Gold/Silver ratio, Oil."""
    components = []

    # Gold — rising gold often means risk-off, but still bullish for holders
    ref = dlm.get_reference_values("gold")
    if ref["current"] != 0:
        s = score_trend(ref)
        components.append(("Gold", s))

    # Silver
    ref = dlm.get_reference_values("silver")
    if ref["current"] != 0:
        s = score_trend(ref)
        components.append(("Silver", s))

    # Gold/Silver ratio — high = risk aversion = bearish
    ratio = dlm.get_ratio("gold", "silver", period="1Y")
    if not ratio.empty:
        current = float(ratio.iloc[-1])
        avg = float(ratio.mean())
        s = score_ratio(current, avg, above_is_bullish=False)
        components.append(("Gold/Silver", s))

    # Oil — rising oil adds inflationary pressure, mildly bearish
    ref = dlm.get_reference_values("oil")
    if ref["current"] != 0:
        s = score_trend(ref, invert=True)
        components.append(("Crude Oil", s))

    return _section_result("Commodities", components)


def score_crypto() -> dict:
    """Crypto: Bitcoin, Ethereum."""
    components = []

    for key, label in [("btc", "Bitcoin"), ("eth", "Ethereum")]:
        ref = dlm.get_reference_values(key)
        if ref["current"] != 0:
            s = score_trend(ref)
            components.append((label, s))

    return _section_result("Crypto", components)


def score_predictive() -> dict:
    """Predictive Signals: forward-looking technical + structural indicators."""
    components = []

    # 1. Moving Average Crossovers — average across SPY, MSCI World, EM
    ma_scores = []
    for key, label in [("spy", "SPY"), ("msci_world", "MSCI World"),
                        ("em", "EM")]:
        status = dlm.get_ma_crossover_status(key, short=50, long=200)
        if status["price"] != 0:
            ma_scores.append(score_ma_crossover(status))
    if ma_scores:
        avg_ma = round(float(np.mean(ma_scores)), 1)
        components.append(("50/200 DMA", avg_ma))

    # 2. VIX Term Structure (backwardation detection)
    vix_ts = dlm.get_vix_term_structure(period="1Y")
    if not vix_ts.empty:
        ratio_val = float(vix_ts.iloc[-1])
        s = score_vix_term_structure(ratio_val)
        components.append(("VIX Term Struct.", s))

    # 3. Rate of Change — S&P 500 momentum (20-day)
    roc = dlm.get_rate_of_change("sp500", periods=20, period_window="1Y")
    if not roc.empty:
        s = score_roc(float(roc.iloc[-1]))
        components.append(("Momentum (ROC)", s))

    # 4. Copper/Gold Ratio — growth expectations
    cu_au = dlm.get_ratio("copper", "gold", period="1Y")
    if not cu_au.empty:
        current = float(cu_au.iloc[-1])
        avg = float(cu_au.mean())
        s = score_ratio(current, avg, above_is_bullish=True)
        components.append(("Copper/Gold", s))

    # 5. Yield Curve Slope Trend
    slope = dlm.get_yield_slope_trend(lookback=20, period="1Y")
    if slope["current_slope"] != 0 or slope["slope_change"] != 0:
        s = score_slope_change(slope["slope_change"])
        components.append(("Yield Slope Trend", s))

    return _section_result("Predictive", components)


# ─────────────────────────────────────────────
# Overall aggregation
# ─────────────────────────────────────────────

def compute_overall_signal() -> dict:
    """Aggregate all sections into one overall market signal.

    Returns:
        {
            "score":        float,        # −100..+100
            "action":       str,          # "BUY" / "HOLD" / …
            "color":        str,          # hex
            "sections":     [section_result, ...],
            "top_bullish":  [(name, score), ...],  # up to 3
            "top_bearish":  [(name, score), ...],  # up to 3
        }
    """
    section_fns = {
        "sentiment":   score_sentiment,
        "rates":       score_rates,
        "equities":    score_equities,
        "commodities": score_commodities,
        "crypto":      score_crypto,
        "predictive":  score_predictive,
    }
    weights = config.SIGNAL_SECTION_WEIGHTS

    sections = []
    weighted_sum = 0.0
    total_weight = 0.0
    all_components = []

    for key, fn in section_fns.items():
        result = fn()
        sections.append(result)
        w = weights.get(key, 0.2)
        weighted_sum += result["score"] * w
        total_weight += w
        all_components.extend(result["components"])

    overall_score = round(weighted_sum / total_weight, 1) if total_weight else 0.0
    action, color = _action_for_score(overall_score)

    # Sort all individual indicator scores
    sorted_components = sorted(all_components, key=lambda x: x[1], reverse=True)
    top_bullish = [(n, s) for n, s in sorted_components if s > 0][:3]
    top_bearish = [(n, s) for n, s in sorted_components if s < 0][-3:]
    top_bearish.reverse()  # most bearish first

    return {
        "score": overall_score,
        "action": action,
        "color": color,
        "sections": sections,
        "top_bullish": top_bullish,
        "top_bearish": top_bearish,
    }
