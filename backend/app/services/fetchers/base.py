import abc
from datetime import datetime

import pandas as pd


class DataFetcher(abc.ABC):
    """
    Abstract base class for data fetchers.
    Defines the standard interface for pulling historical OHLCV data.
    """

    @abc.abstractmethod
    async def fetch_historical_data(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data.

        Args:
            symbol: The instrument symbol (e.g., 'XAUUSD', 'EURUSD', 'AAPL').
            timeframe: The requested timeframe (e.g., 'M1', 'M5', 'H1', 'D1').
            start: The start datetime.
            end: The end datetime.

        Returns:
            A pandas DataFrame with standard columns:
            ['time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']
            The 'time' column should be a timezone-aware datetime index or column.
        """
        pass
