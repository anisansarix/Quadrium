import os

files = {
    "README.md": "# Quadrium Foundation\n\nA research-first quantitative trading platform for FX and XAUUSD, built on determinism, strict execution boundaries, and reproducible RL workflows.\n",
    "docs/FOUNDATION_ARCHITECTURE.md": "# Foundation Architecture\n\n- FastAPI Backend\n- Minimal React Frontend\n- Domain-driven design with explicit data, risk, and execution contracts.\n- No direct RL to MT5 connection.\n",
    "docs/DATA_CONTRACTS.md": "# Data Contracts\n\nDefines immutable `MarketBar`, `MarketTick`, `Quote`, and `InstrumentSpec` models, ensuring normalized UTC timestamps and broker-agnostic representations.\n",
    "docs/RISK_CONTRACT.md": "# Risk Contract\n\n`RiskEngine` sits between strategy signals (`OrderIntent` / `TargetPosition`) and `ApprovedOrder`. It deterministically enforces `RiskPolicy` on every tick.\n",
    "docs/EXECUTION_CONTRACT.md": "# Execution Contract\n\n`ApprovedOrder` is passed to adapters (`MT5Provider`, `PaperProvider`). The default is RESEARCH. All operations are typed.\n",
    "docs/SIMULATOR_SPEC.md": "# Simulator Spec\n\nA deterministic engine tracking positions, pnl, margin, and costs. Separated entirely from the `Gymnasium` environment.\n",
    "docs/EXPERIMENT_SPEC.md": "# Experiment Spec\n\nTracks `git_sha`, `dataset_hash`, `seed`, `environment_version` and is immutable once started.\n",
    "docs/adr/001-risk-boundary.md": "# ADR 001: Risk Boundary\n\nRiskEngine is authoritative. The RL agent must never have final say on execution risk.\n",
    "docs/adr/002-target-position-interface.md": "# ADR 002: Target Position Interface\n\nAgents emit `TargetPosition` to decouple signal generation from position accounting.\n",
    "docs/adr/003-market-data-schema.md": "# ADR 003: Market Data Schema\n\nAll timestamps are UTC. Data is immutable. Spread and real volume are explicitly modeled.\n",
    "docs/adr/004-simulator-gym-separation.md": "# ADR 004: Simulator vs Gym Separation\n\nThe Gym environment wraps a domain Simulator, preventing leaked abstractions.\n",
    "docs/adr/005-mt5-boundary.md": "# ADR 005: MT5 Boundary\n\nMetaTrader5 is isolated to `data/providers/mt5.py` and `execution/mt5.py`.\n",
    "docs/adr/006-experiment-lineage.md": "# ADR 006: Experiment Lineage\n\nExperiments require explicit hashing of all code, config, and data before execution begins.\n",
    "docs/adr/007-job-execution.md": "# ADR 007: Job Execution Model\n\nPersistent local worker architecture over FastAPI `BackgroundTasks`.\n"
}

for filepath, content in files.items():
    with open(filepath, 'w') as f:
        f.write(content)
