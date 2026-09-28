from abc import ABC, abstractmethod


class SwapModel(ABC):
    @abstractmethod
    def calculate_swap(self, symbol: str, volume: float, is_long: bool, days_held: int) -> float:
        pass

class ZeroSwapModel(SwapModel):
    def calculate_swap(self, symbol: str, volume: float, is_long: bool, days_held: int) -> float:
        return 0.0
