from abc import ABC, abstractmethod

class CurrencyConversionModel(ABC):
    @abstractmethod
    def convert_to_account_currency(self, amount: float, source_currency: str) -> float:
        pass

class DeterministicUSDModel(CurrencyConversionModel):
    """
    Deterministic currency model that strictly supports USD accounts where the quote currency is also USD (e.g. EURUSD, XAUUSD).
    Rejects any cross pairs (e.g. EURGBP) or different account currencies.
    """
    def __init__(self, account_currency: str = "USD"):
        if account_currency != "USD":
            raise ValueError(f"DeterministicUSDModel currently strictly requires USD account, got {account_currency}")
        self.account_currency = account_currency

    def convert_to_account_currency(self, amount: float, source_currency: str) -> float:
        if source_currency != "USD":
            raise ValueError(f"Unsupported source currency {source_currency}. Deterministic simulator only supports pairs where quote/profit currency is USD.")
        return amount
