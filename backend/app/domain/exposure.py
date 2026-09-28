
from pydantic import BaseModel


class TargetExposure(BaseModel):
    """
    Requested exposure for a specific symbol.
    target_weight is in [-1.0, 1.0], representing the desired fraction of the maximum allowed portfolio exposure.
    """
    symbol: str
    target_weight: float 

class ExposureLimit(BaseModel):
    """
    Defines the absolute exposure bounds for a specific account.
    All values are denominated in the Account Currency.
    """
    max_gross_notional: float
    max_net_notional: float
    max_margin_usage: float

class PortfolioExposure(BaseModel):
    """
    Current real exposure of the portfolio.
    All values denominated in Account Currency.
    """
    gross_notional: float
    net_notional: float
    margin_used: float

class PositionSizingResult(BaseModel):
    """
    The result of converting a TargetExposure into concrete broker units.
    """
    symbol: str
    proposed_volume: float
    account_currency_notional: float
    margin_required: float
    rejected: bool
    rejection_reason: str | None = None
