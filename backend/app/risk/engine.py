from app.domain.models import RiskContext, OrderIntent, TargetPosition, RiskPolicy, RiskDecision, RiskDecisionState, OrderSide, Position
from typing import Union

class RiskEngine:
    def evaluate(self, context: RiskContext, intent: Union[OrderIntent, TargetPosition], policy: RiskPolicy) -> RiskDecision:
        # Determine intent volume
        if isinstance(intent, OrderIntent):
            intended_volume = intent.volume
            side = intent.side
            target_symbol = intent.symbol
        else:
            target_symbol = intent.symbol
            # Simple volume calculation logic based on current position
            current_pos = sum([p.volume if p.side == OrderSide.BUY else -p.volume for p in context.open_positions if p.symbol == target_symbol])
            intended_net = intent.target_volume
            diff = intended_net - current_pos
            intended_volume = abs(diff)
            side = OrderSide.BUY if diff > 0 else OrderSide.SELL

        if intended_volume == 0:
            return RiskDecision(state=RiskDecisionState.APPROVE, reason="No volume change")

        # Spread check
        if context.current_quote.ask - context.current_quote.bid > policy.max_spread_pts * context.instrument.point:
            return RiskDecision(state=RiskDecisionState.REJECT, reason="Spread too high")
            
        # Drawdown check
        if context.account.balance > 0:
            drawdown = (context.account.balance - context.account.equity) / context.account.balance
            if drawdown > policy.max_drawdown_pct:
                return RiskDecision(state=RiskDecisionState.REJECT, reason="Max drawdown exceeded")

        # Valid volume
        if intended_volume < context.instrument.volume_min:
            return RiskDecision(state=RiskDecisionState.REJECT, reason="Volume below minimum")

        # SL required
        if policy.require_sl:
            if isinstance(intent, OrderIntent) and intent.sl is None:
                return RiskDecision(state=RiskDecisionState.REJECT, reason="SL is required")

        if intended_volume > context.instrument.volume_max:
            return RiskDecision(state=RiskDecisionState.CLAMP, reason="Volume exceeds max", clamped_volume=context.instrument.volume_max)

        return RiskDecision(state=RiskDecisionState.APPROVE, reason="Approved")
