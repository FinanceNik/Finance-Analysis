import logging
import pandas as pd
import yfinance as yf
from time import sleep
import numpy as np
import config

logger = logging.getLogger(__name__)


def fetch_historical_data_yfinance():
    try:
        tickers = pd.read_csv("data/mapping.csv", sep=",")["ticker"].unique().tolist()
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

            sleep(0)
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

            sleep(0)
        except Exception as e:
            logger.warning("Failed to fetch benchmark data for %s: %s", bench_ticker, e)

    if combined_df.empty:
        logger.warning("No historical data fetched for any ticker.")
        return

    combined_df_log = np.log10(combined_df + 1e-9)  # Add small value to avoid log(0)
    combined_df_log.index = combined_df_log.index.strftime("%Y-%m-%d")
    combined_df_log.index.name = "date"
    combined_df_log.to_csv("data/historical_data.csv", index=True)
