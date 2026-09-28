from abc import ABC, abstractmethod

class CommissionModel(ABC):
    @abstractmethod
    def calculate_commission(self, symbol: str, volume: float) -> float:
        pass

class ZeroCommissionModel(CommissionModel):
    def calculate_commission(self, symbol: str, volume: float) -> float:
        return 0.0

class FixedPerLotCommissionModel(CommissionModel):
    def __init__(self, rate_per_lot: float = 3.0):
        self.rate_per_lot = rate_per_lot

    def calculate_commission(self, symbol: str, volume: float) -> float:
        return self.rate_per_lot * volume
