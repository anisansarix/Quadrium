from app.domain.models import ApprovedOrder, RiskDecision, RiskDecisionState
from app.simulator.engine import ExecutionResult, SimulatorEngine


class DecisionExecutor:
    def __init__(self, simulator: SimulatorEngine):
        self.simulator = simulator
        
    def execute(self, decision: RiskDecision, approved_order: ApprovedOrder | None = None) -> ExecutionResult | None:
        if decision.state == RiskDecisionState.FREEZE:
            self.simulator.freeze_account()
            return None
        elif decision.state == RiskDecisionState.FLATTEN:
            cts, fills = self.simulator.flatten_and_freeze()
            return ExecutionResult(success=True, fills=fills, closed_trades=cts)
        elif decision.state in [RiskDecisionState.APPROVE, RiskDecisionState.CLAMP] and approved_order:
            return self.simulator.submit_order(approved_order)
            
        return None
