from abc import ABC, abstractmethod

import numpy as np

from app.domain.models import Quote, TargetPosition
from app.strategies.history import RollingHistory


class Strategy(ABC):
    @abstractmethod
    def next(self, current_quote: Quote, history: RollingHistory) -> TargetPosition | None:
        pass

class SMATrend(Strategy):
    def __init__(self, symbol: str, fast_period: int = 10, slow_period: int = 20, target_weight: float = 1.0):
        self.symbol = symbol
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.target_weight = target_weight

    def next(self, current_quote: Quote, history: RollingHistory) -> TargetPosition | None:
        if history.count < self.slow_period:
            return None
            
        closes = history.get_closes()
        fast_sma = np.mean(closes[-self.fast_period:])
        slow_sma = np.mean(closes[-self.slow_period:])
        
        if fast_sma > slow_sma:
            return TargetPosition(symbol=self.symbol, target_weight=self.target_weight)
        elif fast_sma < slow_sma:
            return TargetPosition(symbol=self.symbol, target_weight=-self.target_weight)
            
        return TargetPosition(symbol=self.symbol, target_weight=0.0)

class NoTrade(Strategy):
    def __init__(self, symbol: str):
        self.symbol = symbol
        
    def next(self, current_quote: Quote, history: RollingHistory) -> TargetPosition | None:
        return TargetPosition(symbol=self.symbol, target_weight=0.0)
