import datetime
from abc import ABC, abstractmethod
from typing import Any


class MT5Client(ABC):
    @abstractmethod
    def initialize(self, path: str | None = None, login: int | None = None, password: str | None = None, server: str | None = None, timeout: int = 60000) -> bool:
        pass
        
    @abstractmethod
    def shutdown(self) -> None:
        pass
        
    @abstractmethod
    def last_error(self) -> tuple[int, str]:
        pass
        
    @abstractmethod
    def symbol_info(self, symbol: str) -> Any:
        pass
        
    @abstractmethod
    def symbol_info_tick(self, symbol: str) -> Any:
        pass
        
    @abstractmethod
    def symbol_select(self, symbol: str, enable: bool) -> bool:
        pass
        
    @abstractmethod
    def copy_rates_range(self, symbol: str, timeframe: int, date_from: datetime.datetime, date_to: datetime.datetime) -> Any:
        pass
        
    @abstractmethod
    def copy_ticks_range(self, symbol: str, date_from: datetime.datetime, date_to: datetime.datetime, flags: int) -> Any:
        pass
        
    @abstractmethod
    def account_info(self) -> Any:
        pass
        
    @abstractmethod
    def order_calc_profit(self, action: int, symbol: str, volume: float, price_open: float, price_close: float) -> float | None:
        pass
        
    @abstractmethod
    def order_calc_margin(self, action: int, symbol: str, volume: float, price: float) -> float | None:
        pass

class RealMT5Client(MT5Client):
    def __init__(self):
        try:
            import MetaTrader5 as mt5
            self.mt5 = mt5
        except ImportError:
            raise ImportError("MetaTrader5 package is missing. Install with 'uv sync --all-extras'")
            
    def initialize(self, path: str | None = None, login: int | None = None, password: str | None = None, server: str | None = None, timeout: int = 60000) -> bool:
        kwargs: dict[str, Any] = {}
        if path is not None: kwargs["path"] = path
        if login is not None: kwargs["login"] = login
        if password is not None: kwargs["password"] = password
        if server is not None: kwargs["server"] = server
        if timeout is not None: kwargs["timeout"] = timeout
        return self.mt5.initialize(**kwargs)

    def shutdown(self) -> None:
        self.mt5.shutdown()
        
    def last_error(self) -> tuple[int, str]:
        return self.mt5.last_error()
        
    def symbol_info(self, symbol: str) -> Any:
        return self.mt5.symbol_info(symbol)
        
    def symbol_info_tick(self, symbol: str) -> Any:
        return self.mt5.symbol_info_tick(symbol)
        
    def symbol_select(self, symbol: str, enable: bool) -> bool:
        return self.mt5.symbol_select(symbol, enable)
        
    def copy_rates_range(self, symbol: str, timeframe: int, date_from: datetime.datetime, date_to: datetime.datetime) -> Any:
        return self.mt5.copy_rates_range(symbol, timeframe, date_from, date_to)
        
    def copy_ticks_range(self, symbol: str, date_from: datetime.datetime, date_to: datetime.datetime, flags: int) -> Any:
        return self.mt5.copy_ticks_range(symbol, date_from, date_to, flags)
        
    def account_info(self) -> Any:
        return self.mt5.account_info()
        
    def order_calc_profit(self, action: int, symbol: str, volume: float, price_open: float, price_close: float) -> float | None:
        return self.mt5.order_calc_profit(action, symbol, volume, price_open, price_close)
        
    def order_calc_margin(self, action: int, symbol: str, volume: float, price: float) -> float | None:
        return self.mt5.order_calc_margin(action, symbol, volume, price)
