import datetime
from dataclasses import dataclass
from typing import Any

from app.data.providers.mt5_client import MT5Client


@dataclass
class FakeSymbolInfo:
    name: str
    digits: int = 5
    point: float = 0.00001
    trade_tick_size: float = 0.00001
    trade_tick_value: float = 1.0
    trade_contract_size: float = 100000.0
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    currency_margin: str = "USD"
    currency_profit: str = "USD"
    trade_calc_mode: int = 0
    trade_exemode: int = 2
    trade_stops_level: int = 0

@dataclass
class FakeAccountInfo:
    currency: str = "USD"
    leverage: int = 100
    trade_mode: int = 0

class FakeMT5Client(MT5Client):
    def __init__(self, currency: str = "USD"):
        self.initialized = False
        self._last_error = (1, "Success")
        self.symbols = {"EURUSD": FakeSymbolInfo(name="EURUSD")}
        self.rates = []
        self.ticks = []
        self.account_currency = currency
        
    def initialize(self, path: str | None = None, login: int | None = None, password: str | None = None, server: str | None = None, timeout: int = 60000) -> bool:
        self.initialized = True
        return True
        
    def shutdown(self) -> None:
        self.initialized = False
        
    def last_error(self) -> tuple[int, str]:
        return self._last_error
        
    def symbol_info(self, symbol: str) -> Any:
        return self.symbols.get(symbol)
        
    def symbol_info_tick(self, symbol: str) -> Any:
        return None
        
    def symbol_select(self, symbol: str, enable: bool) -> bool:
        if symbol not in self.symbols:
            self._last_error = (-1, "Symbol not found")
            return False
        return True
        
    def copy_rates_range(self, symbol: str, timeframe: int, date_from: datetime.datetime, date_to: datetime.datetime) -> Any:
        if symbol not in self.symbols:
            self._last_error = (-1, "Symbol not found")
            return None
        import numpy as np
        if not self.rates:
            self._last_error = (-1, "No data")
            return None
            
        start_ts = int(date_from.timestamp())
        end_ts = int(date_to.timestamp())
        filtered = [r for r in self.rates if start_ts <= r[0] <= end_ts]
        
        if not filtered:
            return None
            
        dt = np.dtype([('time', '<i8'), ('open', '<f8'), ('high', '<f8'), ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<u8'), ('spread', '<i4'), ('real_volume', '<u8')])
        return np.array(filtered, dtype=dt)
        
    def copy_ticks_range(self, symbol: str, date_from: datetime.datetime, date_to: datetime.datetime, flags: int) -> Any:
        if symbol not in self.symbols:
            self._last_error = (-1, "Symbol not found")
            return None
        import numpy as np
        if not self.ticks:
            self._last_error = (-1, "No data")
            return None
            
        start_ts = int(date_from.timestamp())
        end_ts = int(date_to.timestamp())
        filtered = [t for t in self.ticks if start_ts <= t[0] <= end_ts]
        
        if not filtered:
            return None
            
        dt = np.dtype([('time', '<i8'), ('bid', '<f8'), ('ask', '<f8'), ('last', '<f8'), ('volume', '<u8'), ('flags', '<u4')])
        return np.array(filtered, dtype=dt)
        
    def account_info(self) -> Any:
        return FakeAccountInfo(currency=self.account_currency)
        
    def order_calc_profit(self, action: int, symbol: str, volume: float, price_open: float, price_close: float) -> float | None:
        if action == 0: # BUY
            return (price_close - price_open) * 100000 * volume
        else:
            return (price_open - price_close) * 100000 * volume
        
    def order_calc_margin(self, action: int, symbol: str, volume: float, price: float) -> float | None:
        return (price * 100000 * volume) / 100.0
