from abc import ABC, abstractmethod


class SlippageModel(ABC):
    @abstractmethod
    def apply_slippage(self, symbol: str, requested_price: float, is_buy: bool) -> float:
        pass

class ZeroSlippageModel(SlippageModel):
    def apply_slippage(self, symbol: str, requested_price: float, is_buy: bool) -> float:
        return requested_price
