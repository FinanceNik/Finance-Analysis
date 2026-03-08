# config.py - Central configuration for the Finance Analysis dashboard

DATA_DIR = "data"

# Risk-free rate for Sharpe ratio calculation
RISK_FREE_RATE = 0.02

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

# Default target allocation for rebalancing (geography → %)
DEFAULT_TARGET_ALLOCATION = {
    "World":  50,
    "US":     20,
    "EU":     15,
    "EM":     10,
    "Crypto":  5,
}
