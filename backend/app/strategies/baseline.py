from abc import ABC, abstractmethod

import pandas as pd

from app.domain.models import Quote, TargetPosition


class Strategy(ABC):
    @abstractmethod
    def next(self, current_quote: Quote, history: pd.DataFrame) -> TargetPosition | None:
        pass

class SMATrend(Strategy):
    def __init__(self, symbol: str, fast_period: int = 10, slow_period: int = 20, target_weight: float = 1.0):
        self.symbol = symbol
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.target_weight = target_weight

    def next(self, current_quote: Quote, history: pd.DataFrame) -> TargetPosition | None:
        if len(history) < self.slow_period:
            return None
            
        fast_sma = history['close'].rolling(window=self.fast_period).mean().iloc[-1]
        slow_sma = history['close'].rolling(window=self.slow_period).mean().iloc[-1]
        
        if fast_sma > slow_sma:
            return TargetPosition(symbol=self.symbol, target_weight=self.target_weight)
        elif fast_sma < slow_sma:
            return TargetPosition(symbol=self.symbol, target_weight=-self.target_weight)
            
        return TargetPosition(symbol=self.symbol, target_weight=0.0)

class NoTrade(Strategy):
    def __init__(self, symbol: str):
        self.symbol = symbol
        
    def next(self, current_quote: Quote, history: pd.DataFrame) -> TargetPosition | None:
        return TargetPosition(symbol=self.symbol, target_weight=0.0)
