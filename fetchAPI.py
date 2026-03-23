import logging
import pandas as pd
import yfinance as yf
import numpy as np
from functools import lru_cache
import config

logger = logging.getLogger(__name__)

# ── Currency pairs to fetch (relative to base currency) ──
_FX_PAIRS = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'SEK', 'NOK', 'DKK']


@lru_cache(maxsize=1)
def fetch_fx_rates(base='CHF') -> dict:
    """Fetch current FX rates from yfinance currency pairs.

    Returns a dict mapping currency code -> rate in base currency.
    E.g. {'USD': 0.88, 'EUR': 0.96, 'CHF': 1.0, ...}
    The rate represents how many units of base currency one unit of
    foreign currency is worth (i.e. multiply foreign amount by rate
    to get base currency amount).
    """
    rates = {base: 1.0}

    for ccy in _FX_PAIRS:
        if ccy == base:
            rates[ccy] = 1.0
            continue
        # yfinance convention: USDCHF=X gives price of 1 USD in CHF
        pair = f"{ccy}{base}=X"
        try:
            ticker = yf.Ticker(pair)
            hist = ticker.history(period="5d")
            if not hist.empty:
                rates[ccy] = float(hist["Close"].dropna().iloc[-1])
            else:
                logger.warning("No FX data for %s — defaulting to 1.0", pair)
                rates[ccy] = 1.0
        except Exception as e:
            logger.warning("Failed to fetch FX rate %s: %s — defaulting to 1.0", pair, e)
            rates[ccy] = 1.0

    return rates


def fetch_historical_data_yfinance():
    try:
        tickers = pd.read_csv("data/mapping.csv", sep=",")["ticker"].unique().tolist()
        # Filter out NaN/empty ticker values (crypto, some Amundi ETFs have no yfinance ticker)
        tickers = [t for t in tickers if pd.notna(t) and str(t).strip()]
    except FileNotFoundError:
        logger.warning("data/mapping.csv not found — skipping historical data fetch.")
        return

    combined_df = pd.DataFrame()

    # Fetch portfolio holdings
    for ticker_symbol in tickers:
        try:
            ticker = yf.Ticker(ticker_symbol)
            historical_data = ticker.history(period="5y")
            close_df = historical_data[["Close"]].rename(columns={"Close": ticker_symbol})

            if combined_df.empty:
                combined_df = close_df
            else:
                combined_df = combined_df.join(close_df, how='outer')

        except Exception as e:
            logger.warning("Failed to fetch data for %s: %s", ticker_symbol, e)

    # Fetch benchmark tickers (SPY, URTH, etc.)
    for bench in config.BENCHMARKS:
        bench_ticker = bench["ticker"]
        if bench_ticker in combined_df.columns:
            continue  # already fetched via mapping
        try:
            ticker = yf.Ticker(bench_ticker)
            historical_data = ticker.history(period="5y")
            close_df = historical_data[["Close"]].rename(columns={"Close": bench_ticker})

            if combined_df.empty:
                combined_df = close_df
            else:
                combined_df = combined_df.join(close_df, how='outer')

        except Exception as e:
            logger.warning("Failed to fetch benchmark data for %s: %s", bench_ticker, e)

    if combined_df.empty:
        logger.warning("No historical data fetched for any ticker.")
        return

    # Consolidate duplicate dates from different exchanges (outer join creates
    # multiple rows per date when exchanges have different trading calendars)
    combined_df = combined_df.groupby(combined_df.index).first()
    combined_df = combined_df.sort_index()

    combined_df_log = np.log10(combined_df + 1e-9)  # Add small value to avoid log(0)
    combined_df_log.index = combined_df_log.index.strftime("%Y-%m-%d")
    combined_df_log.index.name = "date"
    combined_df_log.to_csv("data/historical_data.csv", index=True)


def fetch_macro_data():
    """Fetch macroeconomic indicator data from Yahoo Finance.

    Downloads 5 years of daily close prices for all tickers in
    config.MACRO_TICKERS and saves raw (non-log) prices to
    data/macro_data.csv.
    """
    tickers = list(config.MACRO_TICKERS.values())
    if not tickers:
        logger.warning("No macro tickers configured — skipping.")
        return

    try:
        raw = yf.download(tickers, period="5y", group_by="ticker",
                          auto_adjust=True, threads=True)
    except Exception as e:
        logger.warning("Batch macro download failed: %s", e)
        return

    if raw.empty:
        logger.warning("No macro data returned from yfinance.")
        return

    # Build a clean DataFrame with one Close column per ticker
    close_frames = []
    ticker_to_key = {v: k for k, v in config.MACRO_TICKERS.items()}

    for ticker in tickers:
        key = ticker_to_key.get(ticker, ticker)
        try:
            if len(tickers) == 1:
                series = raw["Close"]
            else:
                series = raw[(ticker, "Close")] if (ticker, "Close") in raw.columns else raw[ticker]["Close"]
            close_frames.append(series.rename(key))
        except Exception as e:
            logger.warning("Could not extract Close for %s: %s", ticker, e)

    if not close_frames:
        logger.warning("No macro close prices extracted.")
        return

    combined = pd.concat(close_frames, axis=1)
    combined.index = pd.to_datetime(combined.index)
    combined = combined.sort_index()
    combined.index = combined.index.strftime("%Y-%m-%d")
    combined.index.name = "date"
    combined.to_csv("data/macro_data.csv", index=True)
    logger.info("Macro data saved: %d rows, %d indicators.",
                len(combined), len(combined.columns))
