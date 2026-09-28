from datetime import datetime

import pandas as pd

from app.data.providers.base import CapabilityMetadata, DataProvider
from app.domain.models import InstrumentSpec


class MT5Capabilities(CapabilityMetadata):
    bid_ask = True
    spread = True
    tick_data = True
    real_volume = True
    broker_metadata = True
    execution_metadata = True
    suitable_for_execution_backtest = True

class MT5Provider(DataProvider):
    def __init__(self, path: str | None = None, login: int | None = None, password: str | None = None, server: str | None = None):
        self.path = path
        self.login = login
        self.password = password
        self.server = server
        self._capabilities = MT5Capabilities()
        self._connected = False

    @property
    def capabilities(self) -> CapabilityMetadata:
        return self._capabilities

    def get_instrument_spec(self, symbol: str) -> InstrumentSpec:
        if not self._connected:
            raise ConnectionError("MT5 Adapter unavailable")
        # In a real implementation we would fetch from MT5
        raise NotImplementedError("Real metadata fetching not implemented")

    def fetch_bars(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        if not self._connected:
            raise ConnectionError("MT5 Adapter unavailable")
        raise NotImplementedError()
