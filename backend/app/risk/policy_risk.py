
from pydantic import BaseModel

from app.simulator.domain import ActionProposal


class PolicyRiskConfig(BaseModel):
    version: str = "1.0"
    max_absolute_weight: float = 1.0
    trading_disabled: bool = False
    # Additional generic controls
    # Notional limits can be enforced at the simulator mapping layer (max_position_units),
    # but weight limits are enforced here.

class RiskDecision(BaseModel):
    requested_action: ActionProposal
    approved_action: ActionProposal
    is_modified: bool
    is_rejected: bool
    reason_code: str
    config_version: str

class DeterministicRiskEngine:
    def __init__(self, config: PolicyRiskConfig):
        self.config = config

    def evaluate(self, action: ActionProposal) -> RiskDecision:
        if self.config.trading_disabled:
            approved = ActionProposal(symbol=action.symbol, target_weight=0.0)
            return RiskDecision(
                requested_action=action,
                approved_action=approved,
                is_modified=True,
                is_rejected=True,
                reason_code="TRADING_DISABLED",
                config_version=self.config.version
            )

        weight = action.target_weight
        clamped_weight = max(
            -self.config.max_absolute_weight,
            min(self.config.max_absolute_weight, weight)
        )

        is_modified = abs(clamped_weight - weight) > 1e-7
        reason = "CLAMPED_TO_MAX_WEIGHT" if is_modified else "APPROVED"

        approved = ActionProposal(symbol=action.symbol, target_weight=clamped_weight)
        
        return RiskDecision(
            requested_action=action,
            approved_action=approved,
            is_modified=is_modified,
            is_rejected=False,
            reason_code=reason,
            config_version=self.config.version
        )
