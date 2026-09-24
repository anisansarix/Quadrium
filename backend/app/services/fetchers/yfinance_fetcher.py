import asyncio
from datetime import datetime

import pandas as pd
import yfinance as yf

from app.core.exceptions import DataError
from app.services.fetchers.base import DataFetcher


class YFinanceFetcher(DataFetcher):
    """
    Data fetcher implementation using Yahoo Finance (yfinance).
    Useful as a fallback when MT5 is not available.
    """

    TIMEFRAME_MAP = {
        "M1": "1m",
        "M5": "5m",
        "M15": "15m",
        "M30": "30m",
        "H1": "1h",
        "H4": "1h",  # We will resample 1h to 4h
        "D1": "1d",
        "W1": "1wk",
        "MN1": "1mo",
    }

    async def fetch_historical_data(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> pd.DataFrame:
        """
        Fetch data from yfinance.
        Note: Yahoo Finance uses different symbols for Forex (e.g. 'EURUSD=X')
        and Crypto (e.g. 'BTC-USD').
        """
        yf_interval = self.TIMEFRAME_MAP.get(timeframe.upper())
        if not yf_interval:
            raise ValueError(f"Timeframe '{timeframe}' is not supported by YFinanceFetcher.")

        # Run the blocking yfinance call in a thread
        loop = asyncio.get_running_loop()

        # Download data
        try:
            df = await loop.run_in_executor(
                None,
                lambda: yf.download(
                    tickers=symbol, start=start, end=end, interval=yf_interval, progress=False
                ),
            )
        except Exception as e:
            raise DataError(f"Failed to fetch data from Yahoo Finance: {e}")

        if df.empty:
            raise DataError(f"No data returned for {symbol} from Yahoo Finance.")

        # If yfinance returns multi-index columns (when multiple tickers or single ticker in newer versions), flatten it
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Map yfinance columns to Quadrium standard columns
        # yfinance columns: 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume'
        df = df.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "real_volume",  # map yf Volume to real_volume
            }
        )

        # Add missing columns with defaults
        df["tick_volume"] = 0
        df["spread"] = 0.0

        # Ensure we only keep the standard columns
        expected_cols = ["open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = 0.0

        df = df[expected_cols]

        # Reset index to make 'time' a column, or just name the index
        df.index.name = "time"

        # Ensure UTC timezone
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")

        # Resample H1 to H4 if requested
        if timeframe.upper() == "H4":
            df = (
                df.resample("4h")
                .agg(
                    {
                        "open": "first",
                        "high": "max",
                        "low": "min",
                        "close": "last",
                        "tick_volume": "sum",
                        "spread": "mean",
                        "real_volume": "sum",
                    }
                )
                .dropna()
            )

        # Convert index back to column for consistency if needed, but keeping it as DatetimeIndex is fine for pandas
        df = df.reset_index()

        return df
