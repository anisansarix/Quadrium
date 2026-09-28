from typing import Any

from pydantic import BaseModel

from app.data.providers.mt5_client import MT5Client
from app.domain.models import InstrumentSpec


class ValidationDiff(BaseModel):
    action: str
    volume: float
    price_open: float
    price_close: float
    quadrium_val: float
    mt5_val: float
    diff_abs: float
    diff_rel: float
    tolerance: float
    passed: bool

class ValidationReport(BaseModel):
    symbol: str
    profit_diffs: list[ValidationDiff]
    margin_diffs: list[ValidationDiff]
    all_passed: bool

def validate_calculations(client: MT5Client, symbol: str, spec: InstrumentSpec, leverage: float = 100.0) -> ValidationReport:
    profit_diffs = []
    margin_diffs = []
    
    scenarios: list[dict[str, Any]] = [
        {"action": 0, "volume": 1.0, "price_open": 1.1000, "price_close": 1.1050},
        {"action": 1, "volume": 1.0, "price_open": 1.1000, "price_close": 1.0950},
        {"action": 0, "volume": 0.5, "price_open": 1.1000, "price_close": 1.1020},
        {"action": 1, "volume": 0.5, "price_open": 1.1000, "price_close": 1.1200},
        {"action": 0, "volume": 2.0, "price_open": 1.1000, "price_close": 1.1100},
    ]
    
    tolerance = 1e-4
    all_passed = True
    
    for s in scenarios:
        mt5_prof = client.order_calc_profit(s["action"], symbol, s["volume"], s["price_open"], s["price_close"])
        
        if s["action"] == 0:
            quad_prof = (s["price_close"] - s["price_open"]) * s["volume"] * spec.contract_size
        else:
            quad_prof = (s["price_open"] - s["price_close"]) * s["volume"] * spec.contract_size
            
        if mt5_prof is not None:
            diff_abs = abs(quad_prof - mt5_prof)
            diff_rel = diff_abs / abs(mt5_prof) if mt5_prof != 0 else diff_abs
            passed = diff_abs <= tolerance
            if not passed: all_passed = False
            
            profit_diffs.append(ValidationDiff(
                action="BUY" if s["action"] == 0 else "SELL",
                volume=s["volume"],
                price_open=s["price_open"],
                price_close=s["price_close"],
                quadrium_val=quad_prof,
                mt5_val=mt5_prof,
                diff_abs=diff_abs,
                diff_rel=diff_rel,
                tolerance=tolerance,
                passed=passed
            ))
            
        mt5_margin = client.order_calc_margin(s["action"], symbol, s["volume"], s["price_open"])
        quad_margin = (s["price_open"] * spec.contract_size * s["volume"]) / leverage
        
        if mt5_margin is not None:
            diff_abs = abs(quad_margin - mt5_margin)
            diff_rel = diff_abs / abs(mt5_margin) if mt5_margin != 0 else diff_abs
            passed = diff_abs <= tolerance
            if not passed: all_passed = False
            
            margin_diffs.append(ValidationDiff(
                action="BUY" if s["action"] == 0 else "SELL",
                volume=s["volume"],
                price_open=s["price_open"],
                price_close=s["price_close"],
                quadrium_val=quad_margin,
                mt5_val=mt5_margin,
                diff_abs=diff_abs,
                diff_rel=diff_rel,
                tolerance=tolerance,
                passed=passed
            ))
            
    return ValidationReport(symbol=symbol, profit_diffs=profit_diffs, margin_diffs=margin_diffs, all_passed=all_passed)
