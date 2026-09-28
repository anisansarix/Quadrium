# PLAN.md

## Project objective

Build a modular research platform for RL-based FX and XAUUSD trading with MT5 as the primary broker/data boundary.

Initial research instruments:
- EURUSD
- GBPUSD
- USDJPY
- XAUUSD

Initial research timeframes:
- M5
- M15
- H1

The project is not considered an execution system until the research, simulator, risk engine, and validation gates are satisfied.

## Phase 0, research repository

Deliver:
- source index
- architecture decision record
- requirements
- domain glossary
- prop-firm rule abstraction
- experiment registry design

Exit criteria:
- every major architectural decision has an explicit rationale
- primary official docs are indexed
- open-source reference repositories are categorized
- unresolved questions are recorded

## Phase 1, data foundation

Build:
- MT5 historical downloader
- raw data storage
- symbol metadata ingestion
- UTC normalization
- schema validation
- duplicate/missing-bar detection
- feature-ready Parquet dataset

Required metadata:
- symbol
- broker
- timeframe
- timezone
- bid/ask availability
- point size
- digits
- contract size
- tick size
- tick value
- volume semantics
- trading sessions
- minimum stop distance where available

Tests:
- chronological ordering
- OHLC invariants
- timestamp invariants
- schema validation
- reproducible data snapshots

## Phase 2, execution-aware simulator

Implement deterministic accounting plus configurable stochastic execution.

Model:
- bid/ask spread
- commission/fees
- slippage
- latency
- order types
- market order fills
- stop-loss
- take-profit
- partial close where applicable
- position lifecycle
- leverage/margin
- swap/financing where relevant
- broker symbol constraints

Do not use a raw close-price fill model as the sole simulator.

Use gym-mtsim as a reference and candidate foundation, not as a guaranteed drop-in production simulator.

## Phase 3, Gymnasium environment

Create a thin environment layer over the simulator.

Candidate action designs:
1. target position
2. direction + bounded conviction
3. direction + bracket structure

Keep sizing risk-aware and preferably outside the policy during the first experiments.

Minimum environment tests:
- reset determinism
- action bounds
- no future leakage
- correct accounting
- correct reward timing
- correct stop/TP behavior
- correct termination behavior
- seed behavior

## Phase 4, risk engine

Create a broker/provider-neutral `RiskPolicy`.

Hard constraints:
- max daily loss
- max total drawdown
- max risk per trade
- max aggregate open risk
- max position size
- max exposure
- max correlated exposure
- max spread
- session restrictions
- event/news restrictions
- weekend restrictions
- mandatory stop-loss
- emergency flattening

The RL agent proposes an action. The risk engine approves, clamps, or rejects it.

## Phase 5, baseline suite

Before claiming RL value, implement non-RL baselines.

Minimum:
- buy and hold where meaningful
- random policy
- no-trade baseline
- simple moving-average trend strategy
- volatility breakout
- ATR-based rule strategy
- fixed-risk momentum baseline

All baselines must use the same simulator and cost assumptions.

## Phase 6, RL benchmark

Start small.

Candidate:
- PPO
- SAC
- TD3
- optionally RLlib implementations for selected experiments

First experiments should use:
- a single symbol
- one timeframe
- a small observation space
- target position or bounded continuous exposure
- deterministic risk engine
- realistic costs

Do not introduce macro/news features until the market-data pipeline is trustworthy.

## Phase 7, evaluation

Use:
- temporal train/validation/test split
- walk-forward analysis
- multiple seeds
- sealed final holdout
- spread stress
- slippage stress
- delayed execution stress
- feature ablation
- symbol transfer tests
- regime slices
- session slices

Track:
- total return
- CAGR where meaningful
- max drawdown
- daily loss distribution
- downside volatility
- Sharpe
- Sortino
- Calmar
- turnover
- average trade
- trade count
- win rate
- profit factor
- exposure
- tail losses
- duration
- rule violations
- rejected actions
- risk clamp rate

Do not optimize one metric in isolation.

## Phase 8, experiment governance

Use MLflow or an equivalent to capture:
- experiment ID
- commit SHA
- dataset fingerprint
- config
- seed
- hyperparameters
- simulator config
- metrics
- artifacts

Use Optuna only after the evaluation protocol is sealed enough to avoid uncontrolled search over the final test set.

## Phase 9, paper/demo execution

MT5 execution adapter:
- market data
- account state
- positions
- pending orders if needed
- order submission
- order result
- reconciliation
- heartbeat
- kill switch

Paper/demo acceptance:
- no duplicate orders
- correct reconciliation
- correct stop placement
- correct restart behavior
- correct handling of terminal disconnect
- correct risk rejection behavior
- audit log complete

## Phase 10, live-readiness gate

Live execution remains disabled unless all are true:
- final holdout is sealed
- tests pass
- risk policy is versioned
- credentials are externalized
- kill switch works
- reconciliation is tested
- paper/demo behavior matches simulator assumptions within known tolerances
- live symbol metadata has been validated
- operator runbook exists
- rollback path exists
- monitoring exists

## Out of scope for first implementation

- high-frequency trading
- direct broker optimization across many venues
- multi-agent RL
- learned execution routing
- automated strategy discovery across thousands of hypotheses
- unbounded hyperparameter sweeps
- fully autonomous live trading
