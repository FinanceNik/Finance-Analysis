import pandas as pd
import yfinance as yf
from time import sleep
import numpy as np

def fetch_historical_data_yfinance():
    tickers = pd.read_csv("data/mapping.csv", sep=",")["ticker"].unique().tolist()
    combined_df = pd.DataFrame()

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
        except:
            pass

    combined_df_log = np.log10(combined_df + 1e-9)  # Add small value to avoid log(0)
    combined_df_log.to_csv("data/historical_data.csv", index=False)
