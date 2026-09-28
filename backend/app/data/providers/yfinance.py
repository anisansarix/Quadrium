from datetime import datetime

import pandas as pd

from app.data.providers.base import CapabilityMetadata, DataProvider
from app.domain.models import InstrumentSpec


class YFinanceCapabilities(CapabilityMetadata):
    bid_ask = False
    spread = False
    tick_data = False
    real_volume = False
    broker_metadata = False
    execution_metadata = False
    suitable_for_execution_backtest = False

class YFinanceProvider(DataProvider):
    def __init__(self, synthetic_specs: bool = False):
        self._capabilities = YFinanceCapabilities()
        self.synthetic_specs = synthetic_specs

    @property
    def capabilities(self) -> CapabilityMetadata:
        return self._capabilities

    def get_instrument_spec(self, symbol: str) -> InstrumentSpec:
        if not self.synthetic_specs:
            raise ValueError("YFinance does not provide true broker execution metadata. Enable synthetic_specs to mock it.")
            
        return InstrumentSpec(
            broker_symbol=symbol,
            canonical_symbol=symbol,
            asset_class="FX",
            digits=5,
            point=0.00001,
            tick_size=0.00001,
            tick_value=1.0,
            contract_size=100000.0,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            margin_currency="USD",
            profit_currency="USD",
            execution_mode="MARKET",
            trading_sessions={"Monday": ["00:00-24:00"]},
            stop_level=0
        )

    def fetch_bars(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"])
        return df
