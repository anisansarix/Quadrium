from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.data.providers.base import CapabilityMetadata, DataProvider
from app.domain.models import InstrumentSpec
from app.data.providers.mt5_client import MT5Client, RealMT5Client


class MT5Capabilities(CapabilityMetadata):
    bid_ask = True
    spread = True
    tick_data = True
    real_volume = True
    broker_metadata = True
    execution_metadata = True
    suitable_for_execution_backtest = False

class MT5Error(Exception):
    pass

class MT5Provider(DataProvider):
    def __init__(self, 
                 path: str | None = None, 
                 login: int | None = None, 
                 password: str | None = None, 
                 server: str | None = None,
                 timeout: int = 60000,
                 client: MT5Client | None = None,
                 symbol_map: dict[str, str] | None = None):
        self.path = path
        self.login = login
        self.password = password
        self.server = server
        self.timeout = timeout
        
        self.client = client if client is not None else RealMT5Client()
        self.symbol_map = symbol_map or {}
        
        self._capabilities = MT5Capabilities()
        self._connected = False

    def _get_broker_symbol(self, canonical_symbol: str) -> str:
        return self.symbol_map.get(canonical_symbol, canonical_symbol)

    def connect(self) -> None:
        if self.client.initialize(path=self.path, login=self.login, password=self.password, server=self.server, timeout=self.timeout):
            self._connected = True
            
            # Phase 1: validate account currency is USD
            account_info = self.client.account_info()
            if account_info is None:
                self._connected = False
                err = self.client.last_error()
                raise MT5Error(f"Failed to fetch account info. Error {err[0]}: {err[1]}")
            if account_info.currency != "USD":
                self._connected = False
                raise MT5Error(f"Unsupported account currency: {account_info.currency}. Only USD accounts are supported in this phase.")
        else:
            err = self.client.last_error()
            raise MT5Error(f"MT5 initialization failed. Error {err[0]}: {err[1]}")

    def disconnect(self) -> None:
        if self._connected:
            self.client.shutdown()
            self._connected = False

    @property
    def capabilities(self) -> CapabilityMetadata:
        return self._capabilities

    def get_instrument_spec(self, symbol: str) -> InstrumentSpec:
        if not self._connected:
            self.connect()
            
        broker_symbol = self._get_broker_symbol(symbol)
        if not self.client.symbol_select(broker_symbol, True):
            err = self.client.last_error()
            raise MT5Error(f"Symbol {broker_symbol} not found or selectable. Error {err[0]}: {err[1]}")
            
        info = self.client.symbol_info(broker_symbol)
        if info is None:
            err = self.client.last_error()
            raise MT5Error(f"Failed to fetch symbol info for {broker_symbol}. Error {err[0]}: {err[1]}")
            
        return InstrumentSpec(
            broker_symbol=info.name,
            canonical_symbol=symbol,
            asset_class="FX", # Assume FX for now
            digits=info.digits,
            point=info.point,
            tick_size=info.trade_tick_size,
            tick_value=info.trade_tick_value,
            contract_size=info.trade_contract_size,
            volume_min=info.volume_min,
            volume_max=info.volume_max,
            volume_step=info.volume_step,
            margin_currency=info.currency_margin,
            profit_currency=info.currency_profit,
            execution_mode="MARKET" if info.trade_mode == 4 else "UNKNOWN", # trade_mode 4 is SYMBOL_TRADE_MODE_FULL
            trading_sessions={},
            stop_level=info.trade_stops_level
        )

    def _map_timeframe(self, timeframe: str) -> int:
        try:
            import MetaTrader5 as mt5
        except ImportError:
            # For testing with fake client where mt5 doesn't exist
            mapping = {"M1": 1, "M5": 5}
            if timeframe not in mapping:
                raise ValueError(f"Unsupported timeframe: {timeframe}")
            return mapping[timeframe]
            
        mapping = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
        }
        if timeframe not in mapping:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return mapping[timeframe]

    def fetch_bars(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        if not self._connected:
            self.connect()
            
        broker_symbol = self._get_broker_symbol(symbol)
        tf = self._map_timeframe(timeframe)
        
        # Ensure UTC
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
            
        start_utc = start.astimezone(timezone.utc)
        end_utc = end.astimezone(timezone.utc)
        
        # In MT5, copy_rates_range takes naive datetimes but assumes they are in UTC
        rates = self.client.copy_rates_range(broker_symbol, tf, start_utc.replace(tzinfo=None), end_utc.replace(tzinfo=None))
        if rates is None or len(rates) == 0:
            err = self.client.last_error()
            raise MT5Error(f"No bars returned for {broker_symbol}. Error {err[0]}: {err[1]}")
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        
        # Check coverage
        returned_start = df['time'].min()
        returned_end = df['time'].max()
        
        # MT5 has limited bars. Validate coverage.
        if returned_start > start_utc:
            raise MT5Error(f"Coverage error: Requested start {start_utc}, but returned data starts at {returned_start}")
        
        df = df.rename(columns={
            "time": "timestamp",
            "tick_volume": "tick_volume",
            "real_volume": "real_volume",
        })
        df["symbol"] = symbol
        df["timeframe"] = timeframe
        
        return df[["timestamp", "symbol", "timeframe", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]

    def fetch_ticks(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        if not self._connected:
            self.connect()
            
        broker_symbol = self._get_broker_symbol(symbol)
        
        # Ensure UTC
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
            
        start_utc = start.astimezone(timezone.utc)
        end_utc = end.astimezone(timezone.utc)
        
        try:
            import MetaTrader5 as mt5
            flags = mt5.COPY_TICKS_ALL
        except ImportError:
            flags = 1 # Fake fallback
            
        ticks = self.client.copy_ticks_range(broker_symbol, start_utc.replace(tzinfo=None), end_utc.replace(tzinfo=None), flags)
        if ticks is None or len(ticks) == 0:
            err = self.client.last_error()
            raise MT5Error(f"No ticks returned for {broker_symbol}. Error {err[0]}: {err[1]}")
            
        df = pd.DataFrame(ticks)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        
        # Validate tick data
        if (df['bid'] <= 0).any() or (df['ask'] <= 0).any():
            raise MT5Error("Validation error: Found non-positive bid/ask prices")
        if (df['bid'] > df['ask']).any():
            raise MT5Error("Validation error: Found bid > ask")
            
        df = df.rename(columns={
            "time": "timestamp",
        })
        df["symbol"] = symbol
        df["spread"] = df["ask"] - df["bid"]
        
        # Explicit sorting and duplicates handling should be documented. Ticks must be monotonic.
        if not df["timestamp"].is_monotonic_increasing:
            raise MT5Error("Validation error: Ticks are not monotonically increasing")
            
        return df[["timestamp", "symbol", "bid", "ask", "last", "volume", "flags"]]
