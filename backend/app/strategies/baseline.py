from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.models import Quote, TargetPosition
import pandas as pd

class Strategy(ABC):
    @abstractmethod
    def next(self, current_quote: Quote, history: pd.DataFrame) -> Optional[TargetPosition]:
        pass

class SMATrend(Strategy):
    def __init__(self, symbol: str, fast_period: int = 10, slow_period: int = 20, volume: float = 0.1):
        self.symbol = symbol
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.volume = volume

    def next(self, current_quote: Quote, history: pd.DataFrame) -> Optional[TargetPosition]:
        if len(history) < self.slow_period:
            return None
            
        fast_sma = history['close'].rolling(window=self.fast_period).mean().iloc[-1]
        slow_sma = history['close'].rolling(window=self.slow_period).mean().iloc[-1]
        
        if fast_sma > slow_sma:
            return TargetPosition(symbol=self.symbol, target_volume=self.volume)
        elif fast_sma < slow_sma:
            return TargetPosition(symbol=self.symbol, target_volume=-self.volume)
            
        return None

class NoTrade(Strategy):
    def __init__(self, symbol: str):
        self.symbol = symbol
        
    def next(self, current_quote: Quote, history: pd.DataFrame) -> Optional[TargetPosition]:
        return TargetPosition(symbol=self.symbol, target_volume=0.0)
