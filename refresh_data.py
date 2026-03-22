#!/usr/bin/env python3
"""Automated data refresh pipeline.

Run standalone to refresh all market data without starting the dashboard:
    python refresh_data.py

Or schedule with cron (e.g., daily at 7am):
    0 7 * * 1-5 cd /path/to/Finance-Analysis && python refresh_data.py
"""
import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    start = datetime.now()
    logger.info("Starting data refresh...")

    # 1. Fetch historical price data for portfolio holdings + benchmarks
    try:
        import fetchAPI
        logger.info("Fetching historical price data...")
        fetchAPI.fetch_historical_data_yfinance()
        logger.info("Historical data updated.")
    except Exception as e:
        logger.error("Historical data fetch failed: %s", e)

    # 2. Fetch macro indicator data
    try:
        logger.info("Fetching macro indicator data...")
        fetchAPI.fetch_macro_data()
        logger.info("Macro data updated.")
    except Exception as e:
        logger.error("Macro data fetch failed: %s", e)

    elapsed = (datetime.now() - start).total_seconds()
    logger.info("Data refresh complete in %.1f seconds.", elapsed)


if __name__ == "__main__":
    sys.exit(main() or 0)
