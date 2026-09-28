# AGENTS.md

## Project identity

This repository is a research-first quantitative trading platform for FX and XAUUSD using reinforcement learning, realistic market simulation, MT5 data and execution, and a hard risk layer.

The system is experimental. Do not represent backtests as proof of live profitability.

## Core engineering principles

1. Separate concerns:
   - data
   - features
   - market simulator
   - trading environment
   - RL policy
   - risk engine
   - execution adapter
   - accounting
   - monitoring
   - evaluation

2. The RL agent must not be the final authority for risk.
   The risk engine is authoritative.

3. Live execution must be isolated behind an explicit adapter.
   Research code must not silently place live orders.

4. Keep research and execution paths structurally similar where possible, but keep broker-specific code at the edge.

5. All market timestamps must be timezone-aware internally and normalized to UTC.

6. Never use future information in features, normalization, labels, reward calculations, or decisions.

7. Every experiment must record:
   - code revision
   - data revision
   - config revision
   - random seed
   - environment parameters
   - simulator parameters
   - model parameters
   - evaluation window
   - result artifacts

8. Prefer typed configuration over magic constants.

9. Prefer deterministic components in:
   - accounting
   - risk checks
   - order validation
   - position sizing
   - PnL calculations
   - compliance/rule enforcement

10. Stochasticity belongs where it models uncertainty:
   - slippage
   - spread variation
   - execution delay
   - synthetic stress scenarios

## Safety around trading

Default development mode is research or demo mode.

Any feature that could submit a live order must require an explicit mode switch and a visible execution boundary.

Never store broker credentials in source control.

Never log secrets.

Never infer account risk limits from assumptions. Load them from a versioned risk policy.

Never bypass a risk veto from the agent.

Never make a live execution call from a unit test.

## Data integrity

Raw data is immutable.

Derived data must retain:
- source
- timestamp range
- symbol
- timeframe
- transformation version
- feature version
- dataset hash where practical

Data validation should detect:
- duplicate timestamps
- missing bars
- non-monotonic timestamps
- invalid OHLC relationships
- impossible prices
- unexpected spread changes
- abnormal gaps
- timezone conversion errors

## RL environment invariants

Every environment must expose:
- observation
- action
- reward
- terminated
- truncated
- info

The environment must clearly document:
- observation timing
- action timing
- fill timing
- transaction cost timing
- stop/limit execution assumptions
- episode boundaries
- position state
- cash/equity accounting

## Evaluation invariants

Do not tune on the final test set.

Use:
- temporal train/validation/test splits
- walk-forward testing
- multiple seeds
- baseline comparisons
- cost stress tests
- leakage tests
- regime and session slices
- final sealed holdout

Do not choose a model solely from peak Sharpe.

Record the full search process so selection bias can be assessed.

## Coding conventions

Primary language: Python.

Use:
- type hints for public interfaces
- dataclasses or Pydantic models for structured config and domain objects where appropriate
- Ruff for linting and formatting
- pytest for tests
- structured logging
- small modules with explicit interfaces

Avoid:
- giant notebooks containing business logic
- hidden global state
- magic risk constants
- hard-coded broker symbol assumptions
- importing MT5 directly into research components
- using pandas operations that silently reorder or shift data without tests

## Antigravity behavior

Before implementing a substantial change:
1. Inspect existing architecture.
2. Identify the relevant spec or plan.
3. State assumptions in the task artifact.
4. Make the smallest coherent change.
5. Run focused tests.
6. Run broader checks when practical.
7. Report what changed and what remains uncertain.

Use project skills in `.agents/skills/` for recurring workflows.

Prefer `AGENTS.md` and `.agents/rules/` for persistent invariants.

Prefer `.agents/skills/*/SKILL.md` for multi-step workflows.
