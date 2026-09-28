# ARCHITECTURE.md

## Design goal

The system should make it easy to swap research methods without rewriting the risk and execution layers.

```text
                 +----------------------+
                 |   Data Acquisition   |
                 | MT5 / files / APIs   |
                 +----------+-----------+
                            |
                            v
                 +----------------------+
                 | Canonical Market Data|
                 | UTC + validated      |
                 +----------+-----------+
                            |
                            v
                 +----------------------+
                 | Feature Engine       |
                 | causal transforms    |
                 +----------+-----------+
                            |
                            v
        +-------------------+--------------------+
        |                                        |
        v                                        v
+------------------+                    +-------------------+
| Baseline Agents  |                    | RL Policy        |
| rules / heuristics|                   | PPO/SAC/TD3/etc. |
+--------+---------+                    +---------+---------+
         |                                        |
         +-------------------+--------------------+
                             |
                             v
                  +-----------------------+
                  | Decision Adapter      |
                  | target exposure /     |
                  | bracket intent        |
                  +-----------+-----------+
                              |
                              v
                  +-----------------------+
                  | HARD RISK ENGINE      |
                  | prop-firm policy      |
                  +-----------+-----------+
                              |
                     approve / clamp / reject
                              |
                              v
                  +-----------------------+
                  | Execution Engine      |
                  | simulator or MT5      |
                  +-----------+-----------+
                              |
                              v
                  +-----------------------+
                  | Accounting + Ledger   |
                  +-----------+-----------+
                              |
                              +-------> Metrics
                              +-------> MLflow
                              +-------> Audit log
```

## Package boundaries

Suggested Python layout:

```text
src/
  core/
    types.py
    clock.py
    errors.py

  data/
    mt5.py
    schema.py
    validation.py
    storage.py

  features/
    indicators.py
    transforms.py
    pipelines.py

  market/
    instruments.py
    quotes.py
    sessions.py
    costs.py

  simulator/
    engine.py
    orders.py
    fills.py
    positions.py
    margin.py
    slippage.py

  envs/
    trading_env.py
    observation.py
    reward.py

  strategies/
    baselines/
    rl/

  risk/
    policy.py
    limits.py
    sizing.py
    correlation.py
    kill_switch.py

  execution/
    interface.py
    mt5.py
    paper.py
    reconciliation.py

  evaluation/
    metrics.py
    walk_forward.py
    robustness.py
    leakage.py

  experiments/
    tracking.py
    registry.py
```

## Key interfaces

### MarketDataProvider

Responsible for:
- historical data
- latest quote
- account symbol metadata
- timezone/session metadata

### Simulator

Responsible for:
- order validation
- order execution
- position lifecycle
- account state
- PnL
- margin
- costs

### Policy

Responsible for:
- reading an observation
- producing an action proposal

It must not directly submit orders.

### RiskEngine

Responsible for:
- evaluating account state
- evaluating proposed action
- clamping or rejecting actions
- enforcing hard limits

### ExecutionAdapter

Responsible for:
- mapping approved orders to broker/external execution
- returning explicit execution results
- reconciliation

## Determinism

Accounting and risk calculations should be deterministic.

The simulator may expose deterministic and stochastic modes.

For stochastic simulation, record:
- seed
- model family
- model parameters

## Research parity

The simulator and live execution adapter should expose compatible domain objects so that:
- research produces `OrderIntent`
- risk transforms it into `ApprovedOrder`
- both paper and live execution consume the same approved order shape

This reduces divergence between backtest and runtime behavior.
