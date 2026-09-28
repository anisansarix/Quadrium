from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd

from app.domain.models import InstrumentSpec


class CapabilityMetadata(ABC):
    bid_ask: bool
    spread: bool
    tick_data: bool
    real_volume: bool
    broker_metadata: bool
    execution_metadata: bool
    suitable_for_execution_backtest: bool

class DataProvider(ABC):
    @property
    @abstractmethod
    def capabilities(self) -> CapabilityMetadata:
        pass

    @abstractmethod
    def get_instrument_spec(self, symbol: str) -> InstrumentSpec:
        pass
        
    @abstractmethod
    def get_broker_metadata(self) -> dict[str, str]:
        pass

    @abstractmethod
    def fetch_bars(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        pass

    @abstractmethod
    def fetch_ticks(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        pass
