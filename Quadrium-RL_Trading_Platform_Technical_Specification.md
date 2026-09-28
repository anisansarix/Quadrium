# Quadrium RL Forex/XAUUSD Trading Platform
## Evidence-Controlled Technical Specification

---

## 1. System Architecture

```
[ MT5 / Parquet Data ] ──> [ Feature Pipeline ] ──> [ Gym Event Simulator ]
                                                           │ (Observation State s_t)
                                                           ▼
[ MT5 Execution Engine ] <── [ RiskPolicy Filter ] <── [ RL Strategy Agent ]
  (Order Requests)             (Hard Gatekeeper)       (Target Weights w_t)
```

### Architectural Decisions

#### Decision 1.1: Strict Decoupling of RL Strategy Policy and Risk Control Engine
* **Decision**: The RL Agent Policy shall act strictly as an unconstrained signal generator outputting normalized target position weights \\(w_t \in [-1.0, 1.0]\\). A separate, deterministic `RiskPolicy` module shall intercept, evaluate, scale, or reject order requests before dispatch to MT5.
* **Evidence**:
  * **VERIFIED FACT**: MT5 `order_send()` executes trades based on exact volume parameters (`MqlTradeRequest`), while `account_info()` exposes live margin and equity constraints.
  * **REPOSITORY CLAIM**: FinRL-X (2026) standardizes trading strategies around `BaseStrategy.generate_weights()` decoupled from execution.
  * **REPOSITORY CLAIM**: `DRL-XAUUSD-Bot` documented that unconstrained pure RL policies fail to maintain capital safety during drawdowns and extreme volatility without deterministic safety filters.
* **Reason**: Neural networks are stochastic function approximators prone to out-of-distribution failure under unexpected market volatility. Hard prop-firm limits (e.g., maximum daily loss, absolute trailing drawdown) must be enforced deterministically outside the neural network state space.
* **Assumptions**: The risk engine runs with near-zero latency prior to order transmission.
* **Risks**: Divergence between the RL policy's intended allocation and executed volume due to risk capping may modify policy dynamics in live execution compared to training simulations.
* **Open Questions**: Should the Gym simulator pass risk-clipped positions back to the agent state \\(s_{t+1}\\), or should the agent observe raw intended positions?

---

## 2. Domain Interfaces & Contracts

### Architectural Decisions

#### Decision 2.1: Python Protocol-Based Contract Abstractions
* **Decision**: All major system subsystems shall be defined via strict Python `typing.Protocol` interfaces.
* **Evidence**:
  * **ENGINEERING RECOMMENDATION**: Decoupled interface protocols enable swapping offline Gymnasium simulators with live MT5 execution bridges without mutating strategy code.
* **Reason**: Ensures module isolation, testability, and explicit boundary guarantees across data ingestion, feature generation, agent inference, risk filtering, and order execution.
* **Assumptions**: Python 3.12+ `typing.Protocol` provides static structural type checking via `mypy`.
* **Risks**: Runtime overhead if type assertions are checked dynamically in high-frequency loops (mitigated by static checking).
* **Open Questions**: Should contracts enforce async execution via `asyncio` for tick handling, or synchronous polling for bar-based (M15) strategies?

### Core Interface Definitions

```python
from typing import Protocol, Dict, Any, List, Optional
from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class AccountState:
    equity: float
    balance: float
    margin_free: float
    margin_level: float
    unrealized_pnl: float
    current_drawdown_pct: float
    daily_drawdown_pct: float

@dataclass(frozen=True)
class TargetAllocation:
    symbol: str
    target_weight: float  # Range [-1.0, 1.0]
    timestamp: pd.Timestamp

@dataclass(frozen=True)
class ScaledOrderRequest:
    symbol: str
    order_type: str       # "BUY", "SELL", "CLOSE"
    volume_lots: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    deviation_pip: int

class IRLStrategy(Protocol):
    def generate_target_weights(self, observation: Dict[str, Any]) -> TargetAllocation:
        ...

class IRiskPolicy(Protocol):
    def evaluate_allocation(
        self, 
        allocation: TargetAllocation, 
        account: AccountState, 
        current_spread_pip: float
    ) -> Optional[ScaledOrderRequest]:
        ...

class IExecutionAdapter(Protocol):
    def execute_order(self, request: ScaledOrderRequest) -> bool:
        ...
```

---

## 3. MT5 Integration Boundary

### Architectural Decisions

#### Decision 3.1: Python MQL5 Native API Bridge
* **Decision**: Data fetching, account status querying, and execution dispatch shall interface directly with MetaTrader 5 via the official `MetaTrader5` Python package using standard MQL5 structures.
* **Evidence**:
  * **VERIFIED FACT**: Official MQL5 Python docs specify `copy_rates_from()`, `copy_rates_from_pos()`, `account_info()`, `positions_get()`, and `order_send()` as primary IPC methods.
* **Reason**: Using the native C-extension API eliminates third-party gateway dependencies and guarantees compatibility with MT5 terminal memory structures.
* **Assumptions**: The deployment environment runs on a Microsoft Windows OS host or a Wine/Docker setup where the MT5 terminal client is running and logged in.
* **Risks**: MT5 Python client interface is synchronous and blocks thread execution during market socket timeouts.
* **Open Questions**: How should connection disconnects during `order_send()` be handled to avoid duplicate execution?

### MT5 Function Mapping Specification

| Subsystem | MT5 Native Function | Function Purpose & Return Handling |
| :--- | :--- | :--- |
| **Historical Ingestion** | `mt5.copy_rates_from_pos()` | Retrieves NumPy array of OHLCV bars (`time`, `open`, `high`, `low`, `close`, `tick_volume`, `spread`, `real_volume`). |
| **Symbol Query** | `mt5.symbol_info()` | Queries symbol contract specifications (`point`, `digits`, `trade_contract_size`, `volume_min`, `volume_step`, `spread`). |
| **Account Telemetry** | `mt5.account_info()` | Queries real-time equity, balance, leverage, margin, and profit. |
| **Position Audit** | `mt5.positions_get()` | Fetches active open positions for portfolio reconciliation. |
| **Order Execution** | `mt5.order_send()` | Dispatches `MqlTradeRequest` structure (`action`, `symbol`, `volume`, `type`, `price`, `sl`, `tp`, `deviation`). |

---

## 4. Market-Data Schema

### Architectural Decisions

#### Decision 4.1: Parquet Storage with Apache Arrow Schema Validation
* **Decision**: All historical bar data, tick data, and processed state features shall be stored in Apache Parquet files versioned by Data Version Control (DVC).
* **Evidence**:
  * **VERIFIED FACT**: MQL5 rates arrays contain structured scalar primitives (`int64` timestamps, `float64` prices, `uint64` volumes) matching columnar binary formats.
  * **ENGINEERING RECOMMENDATION**: Parquet enables Zero-Copy memory mapping into PyTorch tensors via Arrow.
* **Reason**: Optimizes I/O disk throughput during RL offline training loops across multi-gigabyte XAUUSD historical datasets.

### Data Schema Definitions

```python
import pyarrow as pa

OHLCV_PARQUET_SCHEMA = pa.schema([
    ('time', pa.int64()),          # POSIX timestamp (seconds)
    ('open', pa.float64()),        # Bar Open Price
    ('high', pa.float64()),        # Bar High Price
    ('low', pa.float64()),         # Bar Low Price
    ('close', pa.float64()),       # Bar Close Price
    ('tick_volume', pa.int64()),   # Tick Volume
    ('spread', pa.int32()),        # Bar Spread in Points
    ('real_volume', pa.int64())    # Real Volume
])
```

---

## 5. Event-Driven Simulator Requirements

### Architectural Decisions

#### Decision 5.1: Gymnasium-Compliant Market Simulator with MT5 Accounting Logic
* **Decision**: Offline training shall use a custom Gymnasium environment (`QuadriumSimEnv`) modeled after `gym-mtsim` accounting logic, incorporating variable dynamic spreads, per-lot commissions, overnight swaps, and intra-bar SL/TP execution checks.
* **Evidence**:
  * **VERIFIED FACT**: `gym-mtsim` models hedge/unhedge accounts, equity, margin, leverage, and margin-call/stop-out thresholds in a Gym environment.
  * **REPOSITORY CLAIM**: `mt5-rl-trader` demonstrates intra-bar High/Low checking for SL/TP breach detection.
* **Reason**: Training an agent on mid-price bars without bid/ask spread and intra-bar SL/TP execution creates lookahead leakage and unachievable backtest returns.
* **Assumptions**: Historical bid/ask spreads recorded in MT5 rate structures reflect realistic market liquidity during normal market hours.
* **Risks**: Intra-bar order execution order (High first vs Low first) is inherently ambiguous in M15 bar aggregates without tick-level backtesting.
* **Open Questions**: Should the simulator use M1 tick simulation inside M15 bars to resolve High/Low sequence ambiguity?

---

## 6. Target-Position RL Action Contract

### Architectural Decisions

#### Decision 6.1: Continuous Target-Position Weight Space `Box(-1.0, 1.0)`
* **Decision**: The RL Agent action space shall be defined as a continuous scalar representing target position exposure: \\(a_t \in [-1.0, 1.0]\\).
* **Evidence**:
  * **REPOSITORY CLAIM**: `DRL-XAUUSD-Bot` and `mt5-rl-trader` show that fixed-lot sizing degrades non-stationarity because equity growth diminishes percentage impact.
  * **ENGINEERING RECOMMENDATION**: Continuous weight outputs naturally interface with capital-proportional position sizing.
* **Reason**: Continuous weights maintain stationarity under account compounding. \\(a_t = +1.0\\) represents maximum allowable net long position, \\(a_t = -1.0\\) represents maximum short position, and \\(a_t = 0.0\\) forces a flat position.

---

## 7. Deterministic RiskPolicy Contract

### Architectural Decisions

#### Decision 7.1: Externalized, Versioned Risk Policy Configuration
* **Decision**: All prop-firm risk controls, drawdown ceilings, exposure caps, and blackout filters shall be driven by external, versioned Hydra YAML configuration files validated via Pydantic. No risk threshold shall be hardcoded.
* **Evidence**:
  * **ENGINEERING RECOMMENDATION**: Prop-firm specifications vary across firms (e.g., 4% daily vs 5% daily, trailing vs static drawdown). Externalized config ensures single-source-of-truth governance.

```yaml
# config/risk/prop_firm_50k.yaml
version: "1.0.0"
account_base_currency: "USD"
max_daily_loss_pct: 0.045        # 4.5% Hard Daily Stop
max_trailing_drawdown_pct: 0.080 # 8.0% Max Trailing Stop
max_risk_per_trade_pct: 0.010    # 1.0% Equity Risk Cap
max_total_leverage: 10.0         # 1:10 Max Leverage
max_spread_pip: 3.5              # Spread Filter Limit
news_filter:
  enabled: true
  blackout_before_min: 30
  blackout_after_min: 30
  high_impact_currencies: ["USD", "EUR"]
emergency_kill_switch: false
```

---

## 8. Execution Adapter Contract

### Architectural Decisions

#### Decision 8.1: State-Reconciling Execution Engine
* **Decision**: The `ExecutionAdapter` shall calculate delta position changes between live positions returned by `positions_get()` and target allocations passed by `RiskPolicy`, executing incremental orders via `order_send()`.
* **Evidence**:
  * **VERIFIED FACT**: MQL5 Python `positions_get()` retrieves active open tickets and current volume.
* **Reason**: Prevents order stacking and handles partial fills, orphan positions, and manual interventions gracefully.

```
Target Weight w_t ──> Risk Scaler ──> Required Volume V_target
                                              │
Live Positions ─────> Position Auditor ──> Current Volume V_current
                                              │
                                              ▼
                                 Delta Volume ΔV = V_target - V_current
                                              │
                                              ▼
                                 Dispatch mt5.order_send()
```

---

## 9. Backtesting & Validation Protocol

### Architectural Decisions

#### Decision 9.1: Combinatorially Symmetric Cross-Validation (CSCV) and Probability of Backtest Overfitting (PBO)
* **Decision**: Model promotion from validation to paper/live deployment shall require passing mandatory DSR and PBO thresholds calculated via CSCV.
* **Evidence**:
  * **VERIFIED FACT**: Bailey et al. (2015) mathematically prove that standard backtesting on historical data overfits to noise when hyperparameter combinations are evaluated across the same time series.
* **Reason**: Prevents selecting "lucky" RL policies that overfit to specific gold or forex market regimes.

### Validation Threshold Policy Configuration

```yaml
# config/evaluation/strict_pbo.yaml
evaluation_policy:
  min_deflated_sharpe_ratio: 0.95
  max_pbo_threshold: 0.10          # PBO must be < 10%
  cscv_number_of_combinations: 16
  min_out_of_sample_sharpe: 1.20
  walk_forward:
    train_months: 24
    validation_months: 6
    test_months: 6
```

---

## 10. Experiment Tracking Requirements

### Architectural Decisions

#### Decision 10.1: Unified MLflow Experiment Audit Trail
* **Decision**: All training runs, Optuna hyperparameter sweeps, feature configurations, DVC data tags, and backtest results shall be logged to an MLflow Tracking server.
* **Evidence**:
  * **VERIFIED FACT**: MLflow provides artifact logging, metric tracking, and model registry lifecycle management.

### Logged Artifact Structure
* **Parameters**: Gym env configs, PPO/SAC hyperparameters, feature list, Hydra config hash, Git commit SHA.
* **Metrics**: Step rewards, Episode Sharpe ratio, Max Drawdown, Win Rate, Profit Factor, CSCV PBO score, Deflated Sharpe Ratio.
* **Artifacts**: PyTorch `.pt` policy weights, TensorBoard event logs, CSCV PBO heatmaps, Trade Log CSV files.

---

## 11. Google Antigravity Project Structure

### Workspace Layout

```
quadrium/
├── .agents/
│   ├── rules/
│   │   ├── 100-risk-decoupling.md
│   │   ├── 200-mt5-boundary.md
│   │   └── 300-pbo-validation.md
│   └── skills/
│       ├── data-ingestion/SKILL.md
│       ├── model-training/SKILL.md
│       └── pbo-evaluation/SKILL.md
├── AGENTS.md
├── ARCHITECTURE.md
├── PLAN.md
├── config/
│   ├── env/
│   ├── model/
│   └── risk/
├── src/
│   └── quadrium/
│       ├── data/
│       ├── features/
│       ├── sim/
│       ├── agent/
│       ├── risk/
│       └── execution/
└── tests/
```

---

## 12. Architectural Decision Records (ADRs) Required Before Coding

1. **ADR-001**: Strict Decoupling of Signal Generation Policy and Risk Enforcement Engine.
2. **ADR-002**: Standardization on Continuous Target-Position Weight Space `Box(-1.0, 1.0)`.
3. **ADR-003**: Adoption of Gymnasium + Stable-Baselines3 + Hydra Stack.
4. **ADR-004**: Mandatory CSCV/PBO Evaluation Gate for Policy Promotion.
5. **ADR-005**: MQL5 Native Python C-Extension Integration Strategy.
6. **ADR-006**: Versioned External Configuration Schema for Prop-Firm Risk Parameters.

---

## 13. Open Research Questions

1. **Intra-Bar High/Low Sequence Ambiguity**: How significantly does High-before-Low vs. Low-before-High intra-bar assumption impact SL/TP breach accuracy in M15 XAUUSD simulation?
2. **Slippage Modeling during Macro Outliers**: What is the probabilistic distribution of execution slippage on MT5 retail brokers during high-impact USD economic events (NFP/FOMC)?
3. **Reward Function Shaping vs Dynamic Drawdown**: Does penalizing policy drawdown directly in the RL reward signal (\\(r_t = \text{Return}_t - \lambda \cdot \text{Drawdown}_t\\)) cause conservative policy collapse compared to pure Sharpe shaping?

---

## 14. Implementation Backlog (Ordered by Dependency)

- [ ] **Task 1: Workspace & Governance Initialization**
  - Create `AGENTS.md`, `ARCHITECTURE.md`, `PLAN.md`, `.agents/rules/*`, and `.agents/skills/*`. Setup Hydra, DVC, and Poetry/Pipenv workspace.
- [ ] **Task 2: MT5 Data Ingestion & Schema Pipeline**
  - Implement `MT5DataFetcher` using `copy_rates_from_pos()` with Arrow schema validation and DVC Parquet versioning.
- [ ] **Task 3: Feature Pipeline & Stationarity Transformation**
  - Build feature engineering modules calculating stationary price features (log returns, RSI, MACD, volatility ratios).
- [ ] **Task 4: Custom Gymnasium Event-Driven Market Simulator**
  - Build `QuadriumSimEnv` implementing bid/ask spreads, dynamic leverage, margin checks, swaps, and intra-bar SL/TP breach logic.
- [ ] **Task 5: Deterministic Risk Engine & Pydantic Config Validation**
  - Build `RiskPolicy` engine with daily loss limits, max trailing drawdown calculation, spread filters, and emergency kill switches.
- [ ] **Task 6: RL Agent Training & Optuna Integration Pipeline**
  - Build SB3 PPO/SAC agent training harness integrated with Optuna hyperparameter tuning and MLflow logging.
- [ ] **Task 7: Quantitative Backtesting & CSCV/PBO Engine**
  - Implement Bailey et al. (2015) CSCV algorithm to calculate Probability of Backtest Overfitting and Deflated Sharpe Ratio.
- [ ] **Task 8: MT5 Live Execution Bridge & Reconciliation Engine**
  - Implement `MT5ExecutionAdapter` mapping target allocation deltas to `order_send()` via `positions_get()` audit loops.
- [ ] **Task 9: End-to-End Paper Trading Integration Test**
  - Execute end-to-end dry run on MT5 Demo account linking live data fetching, feature generation, agent inference, risk filtering, and execution.

---