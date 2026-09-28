import math

from app.domain.models import (
    AccountState,
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
        
        if context.account.state in [AccountState.FREEZE, AccountState.FLATTEN_AND_FREEZE]:
            return self._reject(context, intent, policy, proposed_target, proposed_volume, ["Account is frozen"])
        
        # 1. Hard Drawdown Breach
        if context.equity_peak > 0:
            drawdown = (context.equity_peak - context.account.equity) / context.equity_peak
            if drawdown >= policy.max_drawdown_pct:
                return self._force_state(context, intent, policy, proposed_target, proposed_volume, RiskDecisionState.FLATTEN, ["Max drawdown exceeded (FLATTEN_AND_FREEZE)"])
                
        # 2. Daily Loss Breach
        daily_loss = context.start_of_day_equity - context.account.equity
        if daily_loss / context.start_of_day_equity >= policy.max_daily_loss_pct:
            return self._force_state(context, intent, policy, proposed_target, proposed_volume, RiskDecisionState.FREEZE, ["Max daily loss exceeded (FREEZE)"])
            
        # 3. Spread Check
        spread_pts = (context.current_quote.ask - context.current_quote.bid) / context.instrument.point
        if spread_pts >= policy.max_spread_pts:
            violations.append(f"Spread {spread_pts} exceeds max {policy.max_spread_pts}")
            
        # 4. Mandatory SL
        if policy.require_sl and intent.sl is None:
            violations.append("Mandatory SL missing")
            
        # Proposed Portfolio math
        open_positions = [p for p in context.open_positions if p.state == PositionState.OPEN]
        current_net_vol = sum([p.volume if p.side == OrderSide.BUY else -p.volume for p in open_positions if p.symbol == intent.symbol])
        intent_delta = intent.volume if intent.side == OrderSide.BUY else -intent.volume
        
        proposed_net_vol = current_net_vol + intent_delta
        is_closing = abs(proposed_net_vol) < abs(current_net_vol) and (current_net_vol * intent_delta < 0)
        is_reversal = (current_net_vol * intent_delta < 0) and abs(intent_delta) > abs(current_net_vol)
        is_opening = not is_closing and not is_reversal
        
        # 5. Position Count
        if is_opening and len(open_positions) >= policy.max_position_count:
            violations.append("Max position count exceeded")
                
        # 6. Volume constraints
        if approved_volume > context.instrument.volume_max:
            approved_volume = context.instrument.volume_max
            state = RiskDecisionState.CLAMP
            reasons.append("Volume clamped to max_volume")
            
        # 7. Leverage & Notional Exposure Limits
        price = context.current_quote.ask if intent.side == OrderSide.BUY else context.current_quote.bid
        
        current_other_gross = sum([p.volume for p in open_positions if p.symbol != intent.symbol])
        proposed_gross_vol = current_other_gross + abs(proposed_net_vol)
        proposed_gross_notional = proposed_gross_vol * context.instrument.contract_size * price
        proposed_net_notional = abs(proposed_net_vol) * context.instrument.contract_size * price
        
        # Gross Exposure
        if policy.max_gross_exposure > 0 and proposed_gross_notional >= policy.max_gross_exposure and not is_closing:
            violations.append("Max gross exposure exceeded")
            
        # Net Exposure
        if policy.max_net_exposure > 0 and proposed_net_notional >= policy.max_net_exposure and not is_closing:
            violations.append("Max net exposure exceeded")
            
        # Leverage limit
        if proposed_gross_notional / context.account.equity > policy.leverage_limit:
            max_gross_vol = (policy.leverage_limit * context.account.equity) / (context.instrument.contract_size * price)
            max_allowed_net_vol_for_symbol = max_gross_vol - current_other_gross
            
            if max_allowed_net_vol_for_symbol < 0:
                violations.append("Leverage limit exceeded")
            else:
                if intent.side == OrderSide.BUY:
                    allowed_delta = max_allowed_net_vol_for_symbol - current_net_vol
                else:
                    allowed_delta = max_allowed_net_vol_for_symbol + current_net_vol 
                    
                allowed_vol = abs(allowed_delta)
                step = context.instrument.volume_step
                allowed_vol = math.floor(allowed_vol / step) * step
                
                if allowed_vol < context.instrument.volume_min:
                    if not is_closing:
                        violations.append("Leverage limit exceeded")
                else:
                    if not is_closing: # Don't clamp a reduction
                        approved_volume = allowed_vol
                        state = RiskDecisionState.CLAMP
                        reasons.append("Volume clamped due to leverage limits")
                        
        # 8. Trade & Open Risk Pct
        if intent.sl is not None:
            # tick_value is cash value per tick per volume unit
            price_distance = abs(price - intent.sl)
            ticks = price_distance / context.instrument.tick_size
            trade_risk_cash = ticks * context.instrument.tick_value * approved_volume
            if trade_risk_cash / context.account.equity >= policy.max_trade_risk_pct:
                violations.append("Max trade risk exceeded")
                
        # Unimplemented explicit TODO
        # TODO: policy.max_open_risk_pct (needs sum of open risk across portfolio)
        # TODO: policy.session_constraints
        
        if violations:
            return self._reject(context, intent, policy, proposed_target, proposed_volume, violations)
            
        return RiskDecision(
            state=state,
            reasons=reasons,
            violations=violations,
            proposed_target=proposed_target,
            approved_target=proposed_target if state != RiskDecisionState.REJECT else 0.0,
            proposed_volume=proposed_volume,
            approved_volume=approved_volume,
            policy_id=policy.id,
            policy_version=policy.version,
            timestamp=context.current_time
        )
        
    def _reject(self, context, intent, policy, target, volume, violations):
        return RiskDecision(
            state=RiskDecisionState.REJECT,
            reasons=[],
            violations=violations,
            proposed_target=target,
            approved_target=0.0,
            proposed_volume=volume,
            approved_volume=0.0,
            policy_id=policy.id,
            policy_version=policy.version,
            timestamp=context.current_time
        )
        
    def _force_state(self, context, intent, policy, target, volume, state, violations):
        return RiskDecision(
            state=state,
            reasons=[],
            violations=violations,
            proposed_target=target,
            approved_target=0.0,
            proposed_volume=volume,
            approved_volume=0.0,
            policy_id=policy.id,
            policy_version=policy.version,
            timestamp=context.current_time
        )
