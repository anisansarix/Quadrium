# Baseline Contract (Phase 5)

## Baseline Interface
All unoptimized heuristic baselines strictly inherit BaselinePolicy, exposing a deterministic predict(MarketObservation) -> ActionProposal mapping.

## Implemented Suites
1. **AlwaysFlat**: Emits 0.0 unconditionally.
2. **AlwaysLong**: Emits 1.0 unconditionally.
3. **AlwaysShort**: Emits -1.0 unconditionally.
4. **SimpleMomentum**: Emits 1.0 if et_1 > 0, else -1.0.
5. **SimpleMeanReversion**: Emits -1.0 if et_1 > 0, else 1.0.

## Backtest Runner
The BacktestRunner loops a given policy through the QuadriumEnv, harvesting identical metrics natively exposed to RL policies to synthesize standard quantitative KPIs (Sharpe, Drawdown, etc.) identically.
