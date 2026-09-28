import math

from app.domain.models import (
    ApprovedOrder,
    OrderIntent,
    OrderSide,
    OrderType,
    RiskContext,
    RiskDecision,
    RiskDecisionState,
    RiskPolicy,
    TargetPosition,
)
from app.risk.engine import RiskEngine


class DecisionPipeline:
    def __init__(self, risk_engine: RiskEngine):
        self.risk_engine = risk_engine

    def _convert_weight_to_volume(self, weight: float, context: RiskContext, policy: RiskPolicy) -> float:
        # Simple translation of weight to lot volume. 
        # weight = 1.0 means full allowed exposure, weight = -1.0 means full short.
        # Max exposure can be based on leverage limit or max_net_exposure.
        # Let's use max_net_exposure as the cap.
        
        max_notional = policy.max_net_exposure
        notional_target = abs(weight) * max_notional
        
        # Calculate lots
        # Notional = volume * contract_size * price (simplification for base currency = account currency)
        # Using current bid/ask for conservative estimation
        price = context.current_quote.ask if weight > 0 else context.current_quote.bid
        target_volume_raw = notional_target / (context.instrument.contract_size * price)
        
        # Quantize to volume_step
        step = context.instrument.volume_step
        quantized_vol = math.floor(target_volume_raw / step) * step
        
        if quantized_vol < context.instrument.volume_min:
            return 0.0
            
        return min(quantized_vol, context.instrument.volume_max)

    def process(self, target: TargetPosition, context: RiskContext, policy: RiskPolicy) -> tuple[ApprovedOrder | None, RiskDecision | None]:
        # 1. Convert weight to proposed volume
        proposed_abs_volume = self._convert_weight_to_volume(target.target_weight, context, policy)
        
        # Current net position
        current_vol = sum([p.volume if p.side == OrderSide.BUY else -p.volume 
                           for p in context.open_positions if p.symbol == target.symbol])
        
        target_net_vol = proposed_abs_volume if target.target_weight > 0 else -proposed_abs_volume
        
        # Desired delta
        delta_vol = target_net_vol - current_vol
        
        if abs(delta_vol) < context.instrument.volume_min:
            return None, None # No operation needed
            
        side = OrderSide.BUY if delta_vol > 0 else OrderSide.SELL
        intent_vol = abs(delta_vol)
        
        intent = OrderIntent(
            symbol=target.symbol,
            side=side,
            type=OrderType.MARKET,
            volume=intent_vol
        )
        
        # 2. Risk Engine Evaluation
        decision = self.risk_engine.evaluate(
            context=context, 
            intent=intent, 
            policy=policy,
            proposed_target=target.target_weight,
            proposed_volume=intent_vol
        )
        
        if decision.state in [RiskDecisionState.APPROVE, RiskDecisionState.CLAMP]:
            final_vol = decision.approved_volume
            if final_vol >= context.instrument.volume_min:
                intent.volume = final_vol
                return ApprovedOrder(
                    intent=intent,
                    risk_decision=decision,
                    timestamp=context.current_time
                ), decision
                
        return None, decision
