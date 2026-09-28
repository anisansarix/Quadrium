from abc import ABC, abstractmethod

class MarginModel(ABC):
    @abstractmethod
    def calculate_margin(self, symbol: str, volume: float, price: float, contract_size: float, leverage: float) -> float:
        pass

class DeterministicMarginModel(MarginModel):
    def calculate_margin(self, symbol: str, volume: float, price: float, contract_size: float, leverage: float) -> float:
        """
        Calculates margin required for a position.
        Assumes price and contract size yield notional in account currency via CurrencyModel guarantees.
        """
        notional = volume * contract_size * price
        return notional / leverage if leverage > 0 else 0.0
