# Risk Engine Contract (Phase 4)

## Architecture Position
The DeterministicRiskEngine is an absolute interceptor separating QuadriumEnv / BaselinePolicy outputs from the exact execution logic of PolicySimulator.

## Risk Configuration
Managed explicitly by PolicyRiskConfig:
- max_absolute_weight: Clamps the extreme boundaries of target exposures (defaults to 1.0).
- 	rading_disabled: Boolean kill-switch.

## Decision Paradigm
The engine ingests an ActionProposal and emits a structured RiskDecision containing:
- Requested target
- Approved target
- is_modified and is_rejected booleans
- Reason code (e.g., CLAMPED_TO_MAX_WEIGHT, APPROVED)
- Configuration version tag.
