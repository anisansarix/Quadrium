# Risk Contract

`RiskEngine` sits between strategy signals (`OrderIntent` / `TargetPosition`) and `ApprovedOrder`. It deterministically enforces `RiskPolicy` on every tick.
