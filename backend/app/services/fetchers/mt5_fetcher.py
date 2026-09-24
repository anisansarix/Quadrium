import asyncio
from datetime import datetime

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from app.core.exceptions import DataError
from app.services.fetchers.base import DataFetcher


class MT5Fetcher(DataFetcher):
    """
    Data fetcher implementation using MetaTrader 5 terminal.
    Requires Windows and the MetaTrader5 Python package.
    """

    def __init__(self) -> None:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 library is not installed or not supported on this OS.")

        self.TIMEFRAME_MAP = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
            "W1": mt5.TIMEFRAME_W1,
            "MN1": mt5.TIMEFRAME_MN1,
        }

    async def fetch_historical_data(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> pd.DataFrame:
        mt5_timeframe = self.TIMEFRAME_MAP.get(timeframe.upper())
        if mt5_timeframe is None:
            raise ValueError(f"Timeframe '{timeframe}' is not supported by MT5Fetcher.")

        loop = asyncio.get_running_loop()

        from app.services.mt5_service import with_resilience

        # MT5 calls must be executed in a thread pool to avoid blocking the asyncio event loop
        @with_resilience
        def _fetch() -> pd.DataFrame:
            assert mt5 is not None
            if not mt5.initialize():
                raise DataError(f"MT5 initialize() failed, error code: {mt5.last_error()}")

            # Request data
            rates = mt5.copy_rates_range(symbol, mt5_timeframe, start, end)
            if rates is None or len(rates) == 0:
                error = mt5.last_error()
                raise DataError(f"No data returned for {symbol}. MT5 error code: {error}")

            df = pd.DataFrame(rates)

            # MT5 returns time as unix timestamps
            df["time"] = pd.to_datetime(df["time"], unit="s")

            # Keep necessary columns
            df = df.rename(
                columns={"real_volume": "real_volume"}
            )  # It's already real_volume in MT5

            expected_cols = [
                "time",
                "open",
                "high",
                "low",
                "close",
                "tick_volume",
                "spread",
                "real_volume",
            ]
            df = df[expected_cols]

            # MT5 times are in broker's timezone.
            # We standardize to UTC. If broker is UTC+2/3, we should ideally shift it,
            # but for simplicity we treat it as UTC localized if not otherwise known,
            # or tz-naive. We will localize it to UTC to match standard interface.
            df["time"] = df["time"].dt.tz_localize("UTC")

            return df

        try:
            return await loop.run_in_executor(None, _fetch)
        except Exception as e:
            raise DataError(f"MT5 Fetch Failed: {e}")
