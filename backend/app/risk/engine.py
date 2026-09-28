
from app.domain.models import (
    OrderIntent,
    OrderSide,
    PositionState,
    RiskContext,
    RiskDecision,
    RiskDecisionState,
    RiskPolicy,
)


class RiskEngine:
    def evaluate(self, context: RiskContext, intent: OrderIntent, policy: RiskPolicy, proposed_target: float, proposed_volume: float) -> RiskDecision:
        reasons = []
        violations = []
        state = RiskDecisionState.APPROVE
        approved_volume = proposed_volume
        
        # 1. Daily Loss Check
        daily_loss = context.start_of_day_equity - context.account.equity
        if daily_loss / context.start_of_day_equity > policy.max_daily_loss_pct:
            violations.append("Max daily loss exceeded")
            
        # 2. Drawdown Check
        if context.equity_peak > 0:
            drawdown = (context.equity_peak - context.account.equity) / context.equity_peak
            if drawdown > policy.max_drawdown_pct:
                violations.append("Max drawdown exceeded")
                
        # 3. Spread Check
        spread_pts = (context.current_quote.ask - context.current_quote.bid) / context.instrument.point
        if spread_pts > policy.max_spread_pts:
            violations.append(f"Spread {spread_pts} exceeds max {policy.max_spread_pts}")
            
        # 4. Mandatory SL
        if policy.require_sl and intent.sl is None:
            violations.append("Mandatory SL missing")
            
        # 5. Position Count
        if len([p for p in context.open_positions if p.state == PositionState.OPEN]) >= policy.max_position_count:
            # allow closes, reject new opens
            current_net = sum([p.volume if p.side == OrderSide.BUY else -p.volume for p in context.open_positions])
            is_opening = (intent.side == OrderSide.BUY and current_net >= 0) or (intent.side == OrderSide.SELL and current_net <= 0)
            if is_opening:
                violations.append("Max position count exceeded")
                
        # 6. Volume constraints
        if approved_volume > context.instrument.volume_max:
            approved_volume = context.instrument.volume_max
            state = RiskDecisionState.CLAMP
            reasons.append("Volume clamped to max_volume")
            
        # 7. Leverage Limit (Notional / Equity)
        price = context.current_quote.ask if intent.side == OrderSide.BUY else context.current_quote.bid
        notional_added = approved_volume * context.instrument.contract_size * price
        
        current_notional = sum([p.volume * context.instrument.contract_size * (context.current_quote.ask if p.side == OrderSide.BUY else context.current_quote.bid) for p in context.open_positions if p.state == PositionState.OPEN])
        
        if (current_notional + notional_added) / context.account.equity > policy.leverage_limit:
            # Attempt to clamp based on available leverage
            max_available_notional = (policy.leverage_limit * context.account.equity) - current_notional
            allowed_vol = max_available_notional / (context.instrument.contract_size * price)
            step = context.instrument.volume_step
            import math
            allowed_vol = math.floor(allowed_vol / step) * step
            
            if allowed_vol < context.instrument.volume_min:
                violations.append("Leverage limit exceeded")
            else:
                approved_volume = allowed_vol
                state = RiskDecisionState.CLAMP
                reasons.append("Volume clamped due to leverage limits")
                
        if violations:
            state = RiskDecisionState.REJECT
            approved_volume = 0.0
            
        return RiskDecision(
            state=state,
            reasons=reasons,
            violations=violations,
            proposed_target=proposed_target,
            approved_target=proposed_target if state != RiskDecisionState.REJECT else 0.0, # simplified
            proposed_volume=proposed_volume,
            approved_volume=approved_volume,
            policy_id=policy.id,
            policy_version=policy.version,
            timestamp=context.current_time
        )
