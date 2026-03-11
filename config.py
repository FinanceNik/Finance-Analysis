# config.py - Central configuration for the Finance Analysis dashboard

DATA_DIR = "data"

# Risk-free rate for Sharpe ratio calculation
RISK_FREE_RATE = 0.02

# Expected annual portfolio return (used for fee drag projections)
EXPECTED_RETURN = 0.08

# Default Monte Carlo parameters
MC_DEFAULT_RUNS = 200
MC_DEFAULT_RETURN = 8       # percent
MC_DEFAULT_VOLATILITY = 18  # percent
MC_DEFAULT_HORIZON = 20     # years

# Default Real Estate parameters
RE_DEFAULT_VALUE = 350_000
RE_DEFAULT_GROWTH = 3       # percent
RE_DEFAULT_INCOME = 1_700   # monthly CHF
RE_DEFAULT_COSTS = 1_200    # monthly CHF
RE_DEFAULT_YEARS = 20

# ETF expense ratios (TER) — manually maintained
ETF_EXPENSE_RATIOS = {
    "AHYQ":   0.0022,  # Amundi MSCI World III — 0.22%
    "CBMEM":  0.0014,  # Amundi MSCI EM — 0.14%
    "SPICHA": 0.0010,  # UBS ETF SPI — 0.10%
    "VGEU":   0.0012,  # Vanguard FTSE Europe — 0.12%
    "WOSC":   0.0045,  # SPDR MSCI World Small Cap — 0.45%
    "XDEM":   0.0025,  # Xtrackers MSCI World Momentum — 0.25%
}

# Benchmark for performance comparison
BENCHMARK_TICKER = "URTH"       # iShares MSCI World ETF
BENCHMARK_NAME = "MSCI World"

BENCHMARKS = [
    {"ticker": "SPY", "name": "S&P 500"},
    {"ticker": "URTH", "name": "MSCI World"},
]

BENCHMARK_NAMES = {b["ticker"]: b["name"] for b in BENCHMARKS}
BENCHMARK_TICKERS = [b["ticker"] for b in BENCHMARKS]

# Default target allocation for rebalancing (geography → %)
DEFAULT_TARGET_ALLOCATION = {
    "World":  50,
    "US":     20,
    "EU":     15,
    "EM":     10,
    "Crypto":  5,
}

# ── Macro indicator tickers (yfinance) ──
MACRO_TICKERS = {
    # Market Sentiment & Volatility
    "vix": "^VIX",
    "put_call": "^PCCE",
    "hyg": "HYG",
    "tlt": "TLT",
    # Rates & Yields
    "us10y": "^TNX",
    "us2y": "2YY=F",
    "us30y": "^TYX",
    "dxy": "DX-Y.NYB",
    # Equity Indices
    "sp500": "^GSPC",
    "msci_world": "URTH",
    "em": "EEM",
    "spy": "SPY",
    # Commodities
    "gold": "GC=F",
    "silver": "SI=F",
    "oil": "CL=F",
    # Crypto
    "btc": "BTC-USD",
    "eth": "ETH-USD",
    # Predictive Signals
    "vix3m": "^VIX3M",     # 3-month VIX for term structure
    "copper": "HG=F",      # Copper futures for growth expectations
}

# Display names for macro indicators
MACRO_NAMES = {
    "vix": "VIX", "put_call": "Put/Call Ratio", "hyg": "HYG", "tlt": "TLT",
    "us10y": "US 10Y Yield", "us2y": "US 2Y Yield", "us30y": "US 30Y Yield",
    "dxy": "Dollar Index",
    "sp500": "S&P 500", "msci_world": "MSCI World", "em": "Emerging Mkts",
    "spy": "SPY",
    "gold": "Gold", "silver": "Silver", "oil": "Crude Oil (WTI)",
    "btc": "Bitcoin", "eth": "Ethereum",
    "vix3m": "VIX 3M", "copper": "Copper",
}

# Threshold-based color coding for sentiment indicators
MACRO_THRESHOLDS = {
    "vix": {"low": 15, "mid": 25, "high": 35},          # <15 calm, >35 panic
    "put_call": {"low": 0.7, "mid": 1.0, "high": 1.3},  # <0.7 bullish, >1.0 bearish
    "dxy": {"low": 95, "mid": 100, "high": 105},         # dollar strength bands
}

# ── Signal Engine Configuration ──
SIGNAL_SECTION_WEIGHTS = {
    "sentiment":   0.20,   # leading indicator — VIX, Put/Call, HYG/TLT
    "rates":       0.15,   # macro backdrop — yield spread, DXY, 10Y trend
    "equities":    0.20,   # market direction — S&P, MSCI, EM
    "commodities": 0.15,   # inflation / risk — Gold, Silver, Oil
    "crypto":      0.10,   # risk appetite tail — BTC, ETH
    "predictive":  0.20,   # forward-looking — MA crosses, VIX term, momentum, Cu/Au, slope
}

# Score-to-action mapping: (min_score, action_text)
# Evaluated top-down; first match where score >= min_score wins.
SIGNAL_ACTIONS = [
    (40,  "BUY",       "#34c759"),   # strongGreen
    (10,  "LEAN BUY",  "#60d394"),   # light green
    (-10, "HOLD",      "#f5a623"),   # amber
    (-40, "LEAN SELL", "#f07167"),   # light red
    (-100, "SELL",     "#ff3b30"),   # strongRed
]

# ── Backtest Configuration ──
BACKTEST_ASSETS = {
    "spy":        {"name": "SPY",    "class": "equity"},
    "msci_world": {"name": "URTH",   "class": "equity"},
    "em":         {"name": "EEM",    "class": "equity"},
    "tlt":        {"name": "TLT",    "class": "bond"},
    "hyg":        {"name": "HYG",    "class": "bond"},
    "gold":       {"name": "Gold",   "class": "commodity"},
    "silver":     {"name": "Silver", "class": "commodity"},
    "oil":        {"name": "Oil",    "class": "commodity"},
    "copper":     {"name": "Copper", "class": "commodity"},
}

BACKTEST_BASE_ALLOCATION = {
    "spy": 0.15, "msci_world": 0.15, "em": 0.08,   # 38% equity
    "tlt": 0.12, "hyg": 0.08,                        # 20% bonds
    "gold": 0.10, "silver": 0.05, "oil": 0.05, "copper": 0.07,  # 27% commodity
}
# Remaining 15% = implicit cash (0% return)

# Signal weights excluding crypto (reweighted to sum ≈ 1.0)
BACKTEST_SIGNAL_WEIGHTS = {
    "sentiment":   0.25,
    "rates":       0.18,
    "equities":    0.22,
    "commodities": 0.18,
    "predictive":  0.17,
}

BACKTEST_MA_WARMUP = 200            # trading days before first signal (200-day MA)
BACKTEST_SENSITIVITY_RANGE = (0.0, 3.0)
BACKTEST_SENSITIVITY_STEPS = 31     # grid search granularity


# Sector mapping for positions (manually maintained)
SECTOR_MAP = {
    "APC":    "Technology",
    "ABEC":   "Technology",
    "307":    "Technology",
    "GOOG":   "Technology",
    "AMZN":   "Technology",
    "QQQM":   "Technology",
    "FTK":    "Financials",
    "AHYQ":   "Diversified",
    "CBMEM":  "Diversified",
    "SPICHA": "Diversified",
    "VGEU":   "Diversified",
    "VFEM":   "Diversified",
    "EIMI":   "Diversified",
    "WOSC":   "Diversified",
    "XDEM":   "Diversified",
    "ETH":    "Crypto",
    "BTC":    "Crypto",
    "BNT":    "Crypto",
    "POL":    "Crypto",
    "LINK":   "Crypto",
}
