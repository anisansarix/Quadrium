from pydantic import BaseModel
from typing import Any
from app.data.providers.mt5_client import MT5Client
from app.domain.models import InstrumentSpec

class ValidationDiff(BaseModel):
    action: str
    volume: float
    price_open: float
    price_close: float
    quadrium_val: float
    mt5_val: float
    diff: float

class ValidationReport(BaseModel):
    symbol: str
    profit_diffs: list[ValidationDiff]
    margin_diffs: list[ValidationDiff]

def validate_calculations(client: MT5Client, symbol: str, spec: InstrumentSpec) -> ValidationReport:
    profit_diffs = []
    margin_diffs = []
    
    scenarios = [
        {"action": 0, "volume": 1.0, "price_open": 1.1000, "price_close": 1.1050}, # BUY
        {"action": 1, "volume": 1.0, "price_open": 1.1000, "price_close": 1.0950}, # SELL
        {"action": 0, "volume": 0.5, "price_open": 1.1000, "price_close": 1.1020}
    ]
    
    for s in scenarios:
        mt5_prof = client.order_calc_profit(s["action"], symbol, s["volume"], s["price_open"], s["price_close"])
        
        # Quadrium deterministic PnL
        if s["action"] == 0:
            quad_prof = (s["price_close"] - s["price_open"]) * s["volume"] * spec.contract_size
        else:
            quad_prof = (s["price_open"] - s["price_close"]) * s["volume"] * spec.contract_size
            
        if mt5_prof is not None:
            profit_diffs.append(ValidationDiff(
                action="BUY" if s["action"] == 0 else "SELL",
                volume=s["volume"],
                price_open=s["price_open"],
                price_close=s["price_close"],
                quadrium_val=quad_prof,
                mt5_val=mt5_prof,
                diff=abs(quad_prof - mt5_prof)
            ))
            
        mt5_margin = client.order_calc_margin(s["action"], symbol, s["volume"], s["price_open"])
        # Quadrium margin
        # Without full leverage limits, simple margin:
        quad_margin = (s["price_open"] * spec.contract_size * s["volume"]) / 100.0 # Assuming leverage 100
        
        if mt5_margin is not None:
            margin_diffs.append(ValidationDiff(
                action="BUY" if s["action"] == 0 else "SELL",
                volume=s["volume"],
                price_open=s["price_open"],
                price_close=s["price_close"],
                quadrium_val=quad_margin,
                mt5_val=mt5_margin,
                diff=abs(quad_margin - mt5_margin)
            ))
            
    return ValidationReport(symbol=symbol, profit_diffs=profit_diffs, margin_diffs=margin_diffs)
