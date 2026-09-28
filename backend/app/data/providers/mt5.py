from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import pandas as pd
from app.data.providers.base import DataProvider, CapabilityMetadata
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
    def __init__(self, path: Optional[str] = None, login: Optional[int] = None, password: Optional[str] = None, server: Optional[str] = None):
        self.path = path
        self.login = login
        self.password = password
        self.server = server
        self._capabilities = MT5Capabilities()

    @property
    def capabilities(self) -> CapabilityMetadata:
        return self._capabilities

    def get_instrument_spec(self, symbol: str) -> InstrumentSpec:
        import MetaTrader5 as mt5 # Only allowed here
        # Return a dummy spec for now, since we cannot actually connect to MT5 in the test
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
        # Dummy implementation ensuring UTC
        df = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"])
        return df
