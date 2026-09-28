from typing import Any

from pydantic import BaseModel

from app.data.providers.mt5_client import MT5Client
from app.domain.models import InstrumentSpec


class ProfitValidationDiff(BaseModel):
    action: str
    volume: float
    price_open: float
    price_close: float
    quadrium_val: float | None
    mt5_val: float | None
    diff_abs: float | None
    diff_rel: float | None
    tolerance: float
    passed: bool
    unsupported: bool = False

class MarginValidationDiff(BaseModel):
    action: str
    volume: float
    price_open: float
    price_close: float
    configured_margin_rate: float
    implied_mt5_margin_rate: float | None
    rate_diff_abs: float | None
    rate_tolerance: float
    theoretical_margin_raw: float | None
    theoretical_margin_normalized: float | None
    mt5_margin: float | None
    diff_raw: float | None
    diff_normalized: float | None
    currency_precision: int
    tolerance: float
    passed: bool
    unsupported: bool = False

class MarginModel(BaseModel):
    leverage: float
    account_currency: str
    margin_calculation_mode: str
    margin_rate: float
    margin_rate_source: str
    account_currency_decimals: int

class ValidationReport(BaseModel):
    symbol: str
    leverage: float
    account_currency: str
    margin_calculation_mode: str
    margin_rate: float
    margin_rate_source: str
    account_currency_decimals: int
    profit_diffs: list[ProfitValidationDiff]
    margin_diffs: list[MarginValidationDiff]
    all_passed: bool

def validate_calculations(client: MT5Client, symbol: str, spec: InstrumentSpec, margin_model: MarginModel) -> ValidationReport:
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
    
    if margin_model.margin_rate <= 0:
        return ValidationReport(
            symbol=symbol,
            leverage=margin_model.leverage,
            account_currency=margin_model.account_currency,
            margin_calculation_mode=margin_model.margin_calculation_mode,
            margin_rate=margin_model.margin_rate,
            margin_rate_source=margin_model.margin_rate_source,
            account_currency_decimals=margin_model.account_currency_decimals,
            profit_diffs=[],
            margin_diffs=[],
            all_passed=False
        )
    
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
            
            profit_diffs.append(ProfitValidationDiff(
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
        
        rate_tolerance = 1e-4
        implied_rate = None
        rate_diff = None
        
        if margin_model.margin_calculation_mode not in ["FOREX", "0"]:
            theoretical_raw = None
            theoretical_norm = None
            diff_raw = None
            diff_norm = None
            passed = False
            unsupported = True
            all_passed = False
        else:
            theoretical_raw = (s["price_open"] * spec.contract_size * s["volume"]) / margin_model.leverage * margin_model.margin_rate
            
            quant_str = "1." + "0" * margin_model.account_currency_decimals if margin_model.account_currency_decimals > 0 else "1"
            from decimal import ROUND_HALF_UP, Decimal
            theoretical_norm = float(Decimal(str(theoretical_raw)).quantize(Decimal(quant_str), rounding=ROUND_HALF_UP))
            
            if mt5_margin is not None:
                diff_raw = abs(theoretical_raw - mt5_margin)
                diff_norm = abs(theoretical_norm - mt5_margin)
                
                # Calculate implied rate: mt5_margin = (price_open * contract_size * volume) / leverage * implied_rate
                # implied_rate = (mt5_margin * leverage) / (price_open * contract_size * volume)
                implied_rate = (mt5_margin * margin_model.leverage) / (s["price_open"] * spec.contract_size * s["volume"])
                rate_diff = abs(implied_rate - margin_model.margin_rate)
                
                # Check both monetary and rate equality
                passed_monetary = diff_norm <= tolerance
                passed_rate = rate_diff <= rate_tolerance
                
                passed = passed_monetary and passed_rate
                unsupported = False
                if not passed: all_passed = False
            else:
                diff_raw = None
                diff_norm = None
                passed = False
                unsupported = False
                all_passed = False
                
        if mt5_margin is not None or unsupported:
            margin_diffs.append(MarginValidationDiff(
                action="BUY" if s["action"] == 0 else "SELL",
                volume=s["volume"],
                price_open=s["price_open"],
                price_close=s["price_close"],
                configured_margin_rate=margin_model.margin_rate,
                implied_mt5_margin_rate=implied_rate,
                rate_diff_abs=rate_diff,
                rate_tolerance=rate_tolerance,
                theoretical_margin_raw=theoretical_raw,
                theoretical_margin_normalized=theoretical_norm,
                mt5_margin=mt5_margin,
                diff_raw=diff_raw,
                diff_normalized=diff_norm,
                currency_precision=margin_model.account_currency_decimals,
                tolerance=tolerance,
                passed=passed,
                unsupported=unsupported
            ))
            
    return ValidationReport(
        symbol=symbol, 
        leverage=margin_model.leverage,
        account_currency=margin_model.account_currency,
        margin_calculation_mode=margin_model.margin_calculation_mode,
        margin_rate=margin_model.margin_rate,
        margin_rate_source=margin_model.margin_rate_source,
        account_currency_decimals=margin_model.account_currency_decimals,
        profit_diffs=profit_diffs, 
        margin_diffs=margin_diffs, 
        all_passed=all_passed
    )
