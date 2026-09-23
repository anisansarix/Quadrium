# Quadrium — Implementation Blueprint

> Personal, local-first AI/ML trading research and development platform for proprietary trading firm challenge preparation.

---

## 1. Project Overview

Quadrium is a **single-user, local-first** platform that supports the full trading research lifecycle:

```text
Market Data → Preprocessing → Feature Engineering → Strategy Research
→ RL/ML Training → Backtesting → Validation → Risk Evaluation
→ Prop-Firm Simulation → Demo Testing → Strategy Generation
→ Optional TradingView/MT5 Deployment
```

**Core problem:** Proprietary trading firm challenges demand strategies that satisfy strict drawdown, daily-loss, profit-target, and consistency constraints. Quadrium provides a reproducible, risk-first research environment where every experiment is recorded, every strategy is validated against configurable prop-firm rules, and deployment artifacts (Pine Script / MQL5) are traceable to their source experiment.

**Non-goals:**
- Live trading (future capability, never default)
- Cloud infrastructure for core functionality
- Multi-user / SaaS architecture
- Real-time latency-sensitive execution

---

## 2. Existing Project Analysis

### 2.1 Current Repository State

The repository at `https://github.com/anisansarix/Quadrium.git` contains a **fresh Vite + React scaffold** — not a mature trading platform. There is no existing backend, ML pipeline, database, or trading integration to preserve.

### 2.2 Folder Structure (as inspected)

```text
quadrium/
├── .agents/                  # ECC agent rules, skills, MCP config
│   ├── mcp_config.json
│   ├── rules/AGENTS.md
│   └── skills/               # ECC skills (hallmark, etc.)
├── @/                        # shadcn/ui installation root
│   ├── components/ui/
│   │   └── button.tsx        # Single shadcn Button component (base-mira style)
│   └── lib/
│       └── utils.ts          # cn() re-export
├── src/
│   ├── App.tsx               # Default Vite "Get started" counter page
│   ├── App.css               # Vite default styles
│   ├── index.css             # Tailwind v4 + shadcn CSS variables (light/dark)
│   ├── main.tsx              # React 19 StrictMode entry
│   └── assets/               # hero.png, react.svg, vite.svg
├── public/                   # favicon.svg, icons.svg
├── design.md                 # Hallmark design system spec (studied-DNA, bento grid)
├── components.json           # shadcn config (base-mira style, Figtree + JetBrains Mono)
├── vite.config.ts            # Vite 8 + React + Tailwind v4 plugin
├── package.json              # React 19, shadcn 4, Tailwind 4, Vite 8
├── tsconfig.json             # Composite TS config
├── eslint.config.js          # Flat config, TS + React hooks
├── skills-lock.json          # Hallmark skill lock
└── .gitignore
```

### 2.3 Key Observations

| Aspect | Finding |
|--------|---------|
| **Frontend framework** | Vite 8 + React 19 + TypeScript 6 — modern, keep as-is |
| **Component library** | shadcn/ui v4 (base-mira style) with `@base-ui/react` — keep |
| **Styling** | Tailwind CSS v4 with `@theme inline` block + shadcn CSS vars — keep |
| **Fonts** | Figtree Variable (sans) + JetBrains Mono Variable (heading/mono) — keep |
| **Design system** | Hallmark design.md locked — preserved as design reference |
| **Backend** | None exists — must be created |
| **Python / ML** | None exists — must be created |
| **Database** | None exists — must be selected and created |
| **MT5 integration** | None exists — must be created |
| **Trading logic** | None exists — must be created |
| **Tests** | None exist — must be created |

### 2.4 Assets to Preserve

- [design.md](file:///d:/Trading/quadrium/design.md) — locked Hallmark design tokens
- [components.json](file:///d:/Trading/quadrium/components.json) — shadcn configuration
- [vite.config.ts](file:///d:/Trading/quadrium/vite.config.ts) — Vite + React + Tailwind setup
- [index.css](file:///d:/Trading/quadrium/src/index.css) — design system CSS variables
- [button.tsx](file:///d:/Trading/quadrium/@/components/ui/button.tsx) — shadcn Button primitive
- `.agents/` configuration — ECC rules and skills
- `.gitignore` — needs extension for Python artifacts

### 2.5 What Must Be Replaced

- [App.tsx](file:///d:/Trading/quadrium/src/App.tsx) — Vite default "Get started" page → Quadrium shell
- [App.css](file:///d:/Trading/quadrium/src/App.css) — Vite default styles → removed
- `src/assets/` — Vite logos → Quadrium branding

---

## 3. Quadrium Architecture

### 3.1 System Topology

```text
┌─────────────────────────────────────────────────────────────────┐
│                    Vite React Frontend (:5173)                  │
│  Dashboard │ Data │ Experiments │ Training │ Backtest │ Risk    │
│  Prop-Sim  │ MT5  │ Pine Gen    │ MQL5 Gen │ Config   │ Logs    │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP / WebSocket
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (:8000)                         │
│                                                                 │
│  ┌────────────┐ ┌──────────────┐ ┌────────────────────────┐    │
│  │ REST API   │ │ WebSocket    │ │ Background Workers     │    │
│  │ (CRUD,     │ │ (training    │ │ (Celery-free: asyncio  │    │
│  │  queries)  │ │  progress,   │ │  + threading for ML)   │    │
│  │            │ │  MT5 events) │ │                        │    │
│  └─────┬──────┘ └──────┬───────┘ └──────────┬─────────────┘    │
│        │               │                    │                   │
│  ┌─────▼───────────────▼────────────────────▼─────────────┐    │
│  │                  Service Layer                          │    │
│  │  DataService │ ExperimentService │ TrainingService      │    │
│  │  BacktestService │ RiskEngine │ PropFirmSimulator       │    │
│  │  MT5Service │ PineGenerator │ MQL5Generator             │    │
│  └─────────────────────┬──────────────────────────────────┘    │
│                         │                                       │
└─────────────────────────┼───────────────────────────────────────┘
                          │
          ┌───────────────┼──────────────────┐
          ▼               ▼                  ▼
   ┌──────────┐   ┌──────────────┐   ┌────────────┐
   │  DuckDB  │   │  File System │   │  MT5       │
   │  (OLAP)  │   │  (Parquet,   │   │  Terminal  │
   │          │   │   models,    │   │  (Windows) │
   │  + SQLite│   │   configs)   │   │            │
   │  (OLTP)  │   │              │   │            │
   └──────────┘   └──────────────┘   └────────────┘
```

### 3.2 Design Rationale

| Decision | Rationale |
|----------|-----------|
| **Monorepo** | Single repo simplifies iteration for a solo developer. Frontend + backend + ML in one tree. |
| **FastAPI** | Async Python, native Pydantic validation, WebSocket support, easy to extend. Already in the Python ecosystem alongside PyTorch/FinRL. |
| **No Celery/Redis** | Over-engineering for a single-user workstation. Use Python `asyncio` + `concurrent.futures.ProcessPoolExecutor` for ML jobs. |
| **DuckDB + SQLite** | DuckDB for analytical queries over market data / backtest results (OLAP). SQLite for transactional state (experiments, configs, job status). Both are embedded, zero-config. |
| **Parquet files** | Columnar storage for bulk market data and feature datasets. DuckDB queries Parquet natively. |
| **WebSocket** | Training progress, MT5 account state, and backtest progress streamed to frontend in real time. |

### 3.3 Layer Responsibilities

| Layer | Responsibility | Technology |
|-------|----------------|------------|
| **Frontend** | UI, visualization, user controls | Vite, React 19, TypeScript, shadcn/ui, Tailwind v4, Recharts/Lightweight Charts |
| **API** | Request routing, validation, auth-free (local) | FastAPI, Pydantic v2, WebSockets |
| **Service** | Business logic, orchestration | Python 3.12+, domain services |
| **ML Engine** | Training, inference, RL environments | FinRL, PyTorch, CUDA, NumPy, Pandas |
| **Risk Engine** | Financial calculations, rule evaluation | Pure Python, deterministic, tested |
| **Data Pipeline** | Ingestion, cleaning, feature engineering | Pandas, Polars, DuckDB |
| **Integration** | MT5 communication, script generation | MetaTrader5 lib, Jinja2 templates |
| **Storage** | Persistence | DuckDB, SQLite, Parquet, filesystem |

---

## 4. Technology Decisions

### 4.1 Frontend

| Choice | Selected | Alternatives Considered | Rationale |
|--------|----------|-------------------------|-----------|
| Build tool | **Vite 8** | Webpack, Turbopack | Already configured. Fastest DX. |
| Framework | **React 19** | Vue, Svelte | Already configured. Largest ecosystem. |
| Type system | **TypeScript 6** | — | Already configured. |
| Components | **shadcn/ui v4** (base-mira) | Radix, Headless UI | Already installed. Composable, accessible. |
| Styling | **Tailwind CSS v4** | CSS Modules, Styled Components | Already configured. Design-token-aligned. |
| Charts | **Recharts** + **TradingView Lightweight Charts** | D3, Plotly, ApexCharts | Recharts for metrics/dashboards. Lightweight Charts for candlestick/OHLC (open-source, by TradingView team). |
| Routing | **React Router v7** | TanStack Router | Mature, well-documented. |
| State | **TanStack Query v5** + React Context | Zustand, Redux | Server-state-first approach fits API-driven architecture. Context for UI state. |
| Icons | **Lucide React** | — | Already in package.json. |

### 4.2 Backend / API

| Choice | Selected | Alternatives Considered | Rationale |
|--------|----------|-------------------------|-----------|
| Framework | **FastAPI** | Flask, Django | Async-native, Pydantic built-in, WebSocket support, auto-generated OpenAPI docs. |
| Validation | **Pydantic v2** | Marshmallow, Cerberus | FastAPI-native, fast, type-safe. |
| Task execution | **asyncio + ProcessPoolExecutor** | Celery + Redis, Dramatiq | Single-user, no external broker needed. ML jobs run in separate processes. |
| ASGI server | **Uvicorn** | Hypercorn | Industry standard for FastAPI. |
| Python version | **3.12+** | — | Best performance, latest typing features. |

### 4.3 Database

> [!IMPORTANT]
> **Dual-database strategy: DuckDB (analytics) + SQLite (state)**

| Aspect | DuckDB | SQLite |
|--------|--------|--------|
| **Purpose** | OLAP — bulk queries over market data, backtest results, trade logs, metrics aggregation | OLTP — experiment metadata, job status, configurations, prop-firm profiles |
| **Data model** | Columnar, optimized for scans and aggregations | Row-based, optimized for point lookups and small writes |
| **Access** | Read-heavy analytical workloads | Read/write transactional workloads |
| **File** | `data/quadrium_analytics.duckdb` | `data/quadrium.db` |
| **Why not PostgreSQL** | Requires server process, over-engineered for single-user local | Same |
| **Why not TimescaleDB** | Requires PostgreSQL server + extension | Same |
| **Why not SQLite-only** | Poor analytical performance on large market-data scans | — |
| **Why not DuckDB-only** | Write-heavy transactional patterns are not DuckDB's strength; concurrent write access is limited | — |

#### What Goes Where

| Data | Storage | Format |
|------|---------|--------|
| Raw market data (OHLCV) | **Filesystem** | Parquet files, partitioned by instrument/timeframe |
| Processed features | **Filesystem** | Parquet files, linked to dataset versions |
| Market data catalog / metadata | **DuckDB** | Table with pointers to Parquet paths |
| Backtest results (trades, equity curves) | **DuckDB** | Tables |
| Aggregated metrics | **DuckDB** | Tables / views |
| Experiment metadata | **SQLite** | Table |
| Model metadata | **SQLite** | Table |
| Job queue / status | **SQLite** | Table |
| Prop-firm rule profiles | **SQLite** | Table (JSON columns for rules) |
| Configuration | **Filesystem** | TOML / YAML files |
| Model artifacts (weights, checkpoints) | **Filesystem** | PyTorch `.pt` files in `models/` |
| Generated scripts (Pine, MQL5) | **Filesystem** | Text files in `strategies/artifacts/` |
| Application logs | **Filesystem** | Structured JSON logs |

### 4.4 ML / FinRL

| Choice | Selected | Rationale |
|--------|----------|-----------|
| Framework | **FinRL** (classic library) | Proven, well-documented, direct PyTorch integration. Upgrade path to FinRL-Trading later. |
| DL framework | **PyTorch 2.x** (with CUDA) | FinRL-native. CUDA for GPU acceleration. |
| RL algorithms | **PPO, SAC, A2C, DDPG, TD3** (via FinRL/Stable-Baselines3) | Standard FinRL algorithms for financial RL. |
| Data processing | **Polars** (primary) + Pandas (FinRL compat) | Polars for speed on large datasets; Pandas where FinRL requires it. |
| Feature engineering | **TA-Lib** + custom features | TA-Lib for standard indicators. Custom features for prop-firm-specific signals. |
| Experiment tracking | **MLflow** (local file mode) | Zero-infrastructure, SQLite backend, mature, integrates with PyTorch/FinRL. |
| Hyperparameter tuning | **Optuna** | Lightweight, local, supports PyTorch natively. |

### 4.5 GPU Strategy (RTX 3050)

> [!WARNING]
> **Confirmed: RTX 3050 Laptop — 4GB dedicated VRAM, 7.6GB shared GPU memory (11.6GB total).** RL model training must be designed for the 4GB dedicated VRAM constraint. Shared memory is usable but significantly slower.

| Strategy | Implementation |
|----------|----------------|
| Mixed precision (FP16) | `torch.amp.autocast` — halves activation memory |
| Small batch sizes | Default 32, adjustable per experiment |
| CPU replay buffers | RL replay buffers stored in RAM, not VRAM |
| Gradient checkpointing | Enable for deeper networks |
| `torch.no_grad()` | Wrap all inference / environment interaction |
| VRAM monitoring | Log `torch.cuda.memory_allocated()` during training |
| CPU fallback | Graceful fallback if CUDA unavailable |

### 4.6 MT5 Integration

| Aspect | Decision |
|--------|----------|
| Library | `MetaTrader5` (official pip package) — Windows only |
| Communication | Direct Python ↔ MT5 terminal via shared memory (no network) |
| Data retrieval | `copy_rates_from_pos`, `copy_ticks_from` for historical data |
| Demo trading | `order_send` with demo account credentials |
| Connection management | Explicit `initialize()` / `shutdown()` lifecycle |
| Credential storage | `.env` file (git-ignored), loaded via `python-dotenv` |
| Error handling | Retry with exponential backoff; circuit breaker for persistent failures |

### 4.7 Script Generation

| Target | Engine | Approach |
|--------|--------|----------|
| **Pine Script v5** | Jinja2 templates | Strategy parameters → template variables → validated Pine Script |
| **MQL5** | Jinja2 templates | Strategy parameters → template variables → validated MQL5 EA |
| **Traceability** | Metadata header | Each generated script includes experiment ID, model version, dataset version, backtest hash |

### 4.8 Other Tooling

| Tool | Purpose |
|------|---------|
| **uv** | Python package manager (fast, reproducible) |
| **Ruff** | Python linting + formatting |
| **pytest** | Python testing |
| **Vitest** | Frontend testing |
| **Playwright** | E2E testing |
| **Structlog** | Structured logging (Python) |
| **python-dotenv** | Environment variable management |
| **Alembic** | SQLite schema migrations (if needed) |

---

## 5. Repository Structure

```text
quadrium/
├── .agents/                        # ECC agent configuration (existing)
├── .env.example                    # Environment variable template
├── .gitignore                      # Extended for Python + data artifacts
│
├── frontend/                       # Vite React application (moved from src/)
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── tsconfig.node.json
│   ├── eslint.config.js
│   ├── components.json
│   ├── design.md                   # Hallmark design system
│   ├── public/
│   │   ├── favicon.svg
│   │   └── icons.svg
│   ├── @/                          # shadcn/ui components
│   │   ├── components/ui/
│   │   └── lib/utils.ts
│   └── src/
│       ├── main.tsx
│       ├── index.css               # Tailwind + shadcn tokens
│       ├── app.tsx                  # Root app with router
│       ├── components/             # Shared UI components
│       │   ├── layout/             # Shell, sidebar, header
│       │   ├── charts/             # Chart wrappers
│       │   └── common/             # Reusable pieces
│       ├── pages/                  # Route pages
│       │   ├── dashboard/
│       │   ├── data/
│       │   ├── experiments/
│       │   ├── training/
│       │   ├── backtest/
│       │   ├── risk/
│       │   ├── prop-sim/
│       │   ├── mt5/
│       │   ├── strategies/
│       │   └── settings/
│       ├── hooks/                  # Custom React hooks
│       ├── lib/                    # Utilities, API client
│       ├── types/                  # TypeScript type definitions
│       └── stores/                 # Client state (TanStack Query config)
│
├── backend/                        # FastAPI Python application
│   ├── pyproject.toml              # uv/pip project config
│   ├── uv.lock
│   ├── alembic.ini
│   ├── alembic/                    # SQLite migrations
│   └── app/
│       ├── __init__.py
│       ├── main.py                 # FastAPI app factory
│       ├── config.py               # Settings (Pydantic BaseSettings)
│       ├── api/                    # API routes
│       │   ├── __init__.py
│       │   ├── router.py           # Root router
│       │   ├── data.py             # Market data endpoints
│       │   ├── datasets.py         # Dataset management
│       │   ├── experiments.py      # Experiment CRUD
│       │   ├── training.py         # Training job management
│       │   ├── backtest.py         # Backtesting endpoints
│       │   ├── risk.py             # Risk engine endpoints
│       │   ├── prop_firm.py        # Prop-firm simulation
│       │   ├── mt5.py              # MT5 integration endpoints
│       │   ├── strategies.py       # Pine/MQL5 generation
│       │   └── ws.py               # WebSocket handlers
│       ├── models/                 # SQLAlchemy / Pydantic models
│       │   ├── __init__.py
│       │   ├── db.py               # Database models (SQLite)
│       │   ├── schemas.py          # Pydantic request/response schemas
│       │   └── enums.py            # Shared enumerations
│       ├── services/               # Business logic
│       │   ├── __init__.py
│       │   ├── data_service.py     # Market data acquisition + storage
│       │   ├── dataset_service.py  # Dataset creation + versioning
│       │   ├── feature_service.py  # Feature engineering
│       │   ├── experiment_service.py
│       │   ├── training_service.py
│       │   ├── backtest_service.py
│       │   ├── risk_engine.py      # Core risk calculations
│       │   ├── prop_firm.py        # Challenge simulation
│       │   ├── mt5_service.py      # MT5 communication
│       │   ├── pine_generator.py   # Pine Script generation
│       │   └── mql5_generator.py   # MQL5 generation
│       ├── ml/                     # ML/FinRL layer
│       │   ├── __init__.py
│       │   ├── environments/       # FinRL trading environments
│       │   │   ├── base.py
│       │   │   ├── forex_env.py
│       │   │   └── metals_env.py
│       │   ├── agents/             # RL agent wrappers
│       │   │   ├── base.py
│       │   │   └── finrl_agents.py
│       │   ├── features/           # Feature engineering pipelines
│       │   │   ├── technical.py
│       │   │   └── custom.py
│       │   ├── training/           # Training orchestration
│       │   │   ├── trainer.py
│       │   │   └── callbacks.py
│       │   └── evaluation/         # Model evaluation
│       │       ├── metrics.py
│       │       └── validation.py
│       ├── core/                   # Cross-cutting concerns
│       │   ├── __init__.py
│       │   ├── database.py         # DB connection management
│       │   ├── logging.py          # Structlog configuration
│       │   ├── events.py           # Event bus for WebSocket
│       │   └── exceptions.py       # Custom exception types
│       └── templates/              # Jinja2 templates
│           ├── pine/               # Pine Script templates
│           └── mql5/               # MQL5 templates
│
├── data/                           # Local data storage (git-ignored)
│   ├── raw/                        # Raw market data (Parquet)
│   │   └── {instrument}/{timeframe}/
│   ├── processed/                  # Processed features (Parquet)
│   │   └── {dataset_version}/
│   ├── quadrium.db                 # SQLite (state)
│   └── quadrium_analytics.duckdb  # DuckDB (analytics)
│
├── models/                         # Trained model artifacts (git-ignored)
│   └── {experiment_id}/
│       ├── model.pt
│       ├── config.json
│       └── metadata.json
│
├── strategies/                     # Generated strategy artifacts
│   ├── pine/
│   └── mql5/
│
├── config/                         # Configuration files
│   ├── instruments.toml            # Supported instruments
│   ├── timeframes.toml             # Timeframe definitions
│   ├── prop_firms/                 # Prop-firm rule profiles
│   │   ├── _template.toml
│   │   ├── ftmo.toml
│   │   └── the5ers.toml
│   └── default.toml                # Default application settings
│
├── tests/                          # Test suite
│   ├── backend/
│   │   ├── unit/
│   │   │   ├── test_risk_engine.py
│   │   │   ├── test_prop_firm.py
│   │   │   ├── test_features.py
│   │   │   └── test_data_service.py
│   │   ├── integration/
│   │   │   ├── test_api.py
│   │   │   ├── test_mt5.py
│   │   │   └── test_training.py
│   │   └── conftest.py
│   └── frontend/
│       ├── unit/
│       └── e2e/
│
├── scripts/                        # Utility scripts
│   ├── setup.py                    # First-time environment setup
│   ├── seed_data.py                # Seed sample market data
│   └── verify_gpu.py              # CUDA/GPU verification
│
├── docs/                           # Project documentation
│   ├── architecture.md
│   ├── api.md
│   └── setup.md
│
├── logs/                           # Application logs (git-ignored)
├── mlruns/                         # MLflow tracking (git-ignored)
│
├── Implementation.md               # This document
└── README.md                       # Project README
```

> [!NOTE]
> The current `src/` directory will be relocated to `frontend/src/`. The root-level `package.json`, `vite.config.ts`, and TypeScript configs move into `frontend/`. The `@/` shadcn directory moves into `frontend/@/`.

---

## 6. Data Architecture

### 6.1 Data Sources

| Source | Data Type | Access Method |
|--------|-----------|---------------|
| **MT5 Terminal** | OHLCV bars, tick data, account info | `MetaTrader5` Python library |
| **Yahoo Finance** | OHLCV (fallback/supplementary) | `yfinance` |
| **FinRL data processors** | Pre-built data pipelines | FinRL `FinRLDataProcessor` |

### 6.2 Data Ingestion Pipeline

```text
Source (MT5/Yahoo)
    │
    ▼
Fetcher  ─────► Raw Parquet  ─────► DuckDB catalog entry
                 (data/raw/)          (instrument, timeframe,
                                       date_range, row_count,
                                       file_path, fetch_date)
```

### 6.3 Data Processing Pipeline

```text
Raw Parquet
    │
    ▼
Cleaner (gap fill, outlier detection, timezone normalization)
    │
    ▼
Feature Engineer (TA indicators + custom features)
    │
    ▼
Processed Parquet  ─────► DuckDB catalog entry
(data/processed/{version}/)   (dataset_id, version, features,
                                date_range, instrument, parent_raw)
```

### 6.4 Dataset Versioning

Each processed dataset is identified by a composite key:

```python
@dataclass(frozen=True)
class DatasetVersion:
    instrument: str          # e.g., "XAUUSD"
    timeframe: str           # e.g., "H1"
    date_start: date
    date_end: date
    features: frozenset[str] # Feature names included
    version: str             # Semantic version or hash
    created_at: datetime
    parent_raw_hash: str     # SHA-256 of source Parquet
```

### 6.5 Data Splitting Strategy

```text
                        Full Dataset
├─────────────────────────────────────────────────────┤
│         Train (60%)      │  Val (20%)  │ Test (20%) │
├──────────────────────────┼─────────────┼────────────┤
│     Model training       │  HP tuning  │  Final eval│
│                          │  Early stop │  OOS test  │
```

Walk-forward validation is also supported:

```text
Window 1: [Train──────][Val──][Test]
Window 2:       [Train──────][Val──][Test]
Window 3:             [Train──────][Val──][Test]
```

---

## 7. ML/FinRL Architecture

### 7.1 Environment Design

```python
class QuadriumTradingEnv(gym.Env):
    """
    Custom Gymnasium environment wrapping FinRL's stock trading env
    with prop-firm constraint awareness.
    """
    # State space: OHLCV + technical indicators + account state
    # Action space: Continuous [-1, 1] mapped to position sizing
    # Reward: Risk-adjusted return (Sharpe-based or custom)
    # Termination: Drawdown breach, daily loss breach, or episode end
```

### 7.2 Agent Layer

```text
AgentFactory
    │
    ├── PPOAgent    (Stable-Baselines3)
    ├── SACAgent    (Stable-Baselines3)
    ├── A2CAgent    (Stable-Baselines3)
    ├── DDPGAgent   (Stable-Baselines3)
    ├── TD3Agent    (Stable-Baselines3)
    └── CustomAgent (future extensibility)
```

### 7.3 Training Pipeline

```text
1. Load Dataset Version
2. Configure Environment (instrument, features, reward fn)
3. Select Agent + Hyperparameters
4. Set random seed
5. Train on Train split
6. Validate on Val split (early stopping)
7. Evaluate on Test split
8. Record to MLflow:
   - Hyperparameters
   - Training curves
   - Validation metrics
   - Test metrics
   - Model artifact (.pt)
   - Dataset version reference
   - Environment config
   - Hardware info (GPU, CUDA version)
   - Random seed
9. Save model to models/{experiment_id}/
10. Log to SQLite (experiment status)
11. Push progress via WebSocket
```

### 7.4 GPU Acceleration

```python
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Training config defaults for RTX 3050
DEFAULT_TRAINING_CONFIG = {
    "batch_size": 64,           # Conservative for 4-8GB VRAM
    "use_amp": True,            # Mixed precision
    "gradient_checkpointing": False,  # Enable for deep nets
    "replay_buffer_device": "cpu",    # Keep replay in RAM
    "num_workers": 4,           # DataLoader workers
    "pin_memory": True,
}
```

### 7.5 Experiment Metadata

Each experiment records:

```python
@dataclass
class ExperimentRecord:
    id: str                     # UUID
    name: str                   # Human-readable
    status: ExperimentStatus    # CREATED, TRAINING, COMPLETED, FAILED
    dataset_version: str        # Reference to DatasetVersion
    instrument: str
    timeframe: str
    agent_type: str             # PPO, SAC, etc.
    hyperparameters: dict       # Full HP config
    reward_function: str        # Reward function identifier
    random_seed: int
    training_config: dict       # Batch size, epochs, etc.
    risk_config: dict           # Prop-firm rules applied
    environment_config: dict    # Env-specific settings
    hardware: dict              # GPU, CUDA, CPU info
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    mlflow_run_id: str | None
    metrics: dict | None        # Final metrics summary
    notes: str
```

---

## 8. MT5 Integration Architecture

### 8.1 Connection Management

```python
class MT5ConnectionManager:
    """
    Manages MT5 terminal lifecycle with health checks,
    reconnection, and circuit breaker.
    """
    def __init__(self, config: MT5Config):
        self.config = config
        self._connected = False
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60
        )

    async def connect(self) -> bool: ...
    async def disconnect(self) -> None: ...
    async def health_check(self) -> MT5Status: ...
```

### 8.2 Data Retrieval

| Function | MT5 API | Quadrium Use |
|----------|---------|--------------|
| Historical bars | `copy_rates_from_pos()` | Initial data loading, gap filling |
| Tick data | `copy_ticks_from()` | High-resolution data for specific analysis |
| Symbol info | `symbol_info()` | Instrument metadata (spread, lot size, etc.) |
| Account info | `account_info()` | Demo account status monitoring |

### 8.3 Demo Trading Workflow

```text
1. Validate strategy passed risk checks
2. Initialize MT5 connection
3. Verify demo account credentials
4. Open position (order_send with demo account)
5. Monitor position via polling loop
6. Record trade events to DuckDB
7. Close position based on strategy logic
8. Update experiment with demo results
9. Shutdown MT5 connection
```

### 8.4 Isolation Guarantees

| Concern | Safeguard |
|---------|-----------|
| Demo vs. live | `MT5Config.account_type` enum, validated at startup. Live trading disabled by default. |
| Credential safety | `.env` file, never committed. `MT5Config` loads from environment. |
| Connection failure | Circuit breaker prevents retry storms. All operations timeout after configurable duration. |
| Order validation | All `order_send` calls pass through `OrderValidator` that checks account type, position limits, and risk constraints. |
| Execution isolation | MT5 operations run in a dedicated thread pool, never block the API event loop. |

---

## 9. Risk Engine

### 9.1 Core Calculations

```python
class RiskEngine:
    """
    Deterministic, stateless risk calculation engine.
    All methods are pure functions operating on trade/equity data.
    """

    @staticmethod
    def max_drawdown(equity_curve: np.ndarray) -> DrawdownResult:
        """Peak-to-trough maximum drawdown (absolute and %)."""

    @staticmethod
    def daily_pnl(trades: list[Trade], timezone: str) -> list[DailyPnL]:
        """Daily P&L with timezone-aware day boundaries."""

    @staticmethod
    def daily_loss(
        trades: list[Trade],
        start_balance: Decimal,
        timezone: str,
        include_floating: bool = True
    ) -> list[DailyLoss]:
        """Daily loss calculation with configurable floating inclusion."""

    @staticmethod
    def drawdown_trailing(
        equity_curve: np.ndarray,
        initial_balance: Decimal
    ) -> TrailingDrawdownResult:
        """Trailing drawdown from highest watermark."""

    @staticmethod
    def profit_factor(trades: list[Trade]) -> Decimal: ...
    @staticmethod
    def sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.0) -> float: ...
    @staticmethod
    def sortino_ratio(returns: np.ndarray, risk_free_rate: float = 0.0) -> float: ...
    @staticmethod
    def expectancy(trades: list[Trade]) -> Decimal: ...
    @staticmethod
    def win_rate(trades: list[Trade]) -> Decimal: ...
    @staticmethod
    def max_consecutive_losses(trades: list[Trade]) -> int: ...
    @staticmethod
    def recovery_factor(net_profit: Decimal, max_dd: Decimal) -> Decimal: ...
    @staticmethod
    def average_r(trades: list[Trade]) -> Decimal: ...
    @staticmethod
    def consistency_score(daily_pnl: list[DailyPnL], threshold_pct: Decimal) -> ConsistencyResult: ...
```

### 9.2 Prop-Firm Rule Architecture

```python
@dataclass
class PropFirmProfile:
    """Configurable prop-firm challenge rules."""
    name: str                           # e.g., "FTMO Challenge"
    account_size: Decimal               # e.g., 10000
    max_overall_drawdown_pct: Decimal   # e.g., 0.10
    drawdown_type: DrawdownType         # STATIC | TRAILING
    max_daily_loss_pct: Decimal         # e.g., 0.05
    daily_loss_includes_floating: bool  # Whether unrealized P&L counts
    daily_reset_timezone: str           # e.g., "Europe/Prague"
    phases: list[ChallengePhase]        # Phase 1, Phase 2, Funded
    consistency_rules: list[ConsistencyRule]  # Optional

@dataclass
class ChallengePhase:
    name: str                           # e.g., "Phase 1"
    profit_target_pct: Decimal          # e.g., 0.10
    min_trading_days: int               # e.g., 4
    max_calendar_days: int | None       # e.g., 30

@dataclass
class ConsistencyRule:
    rule_type: ConsistencyType          # MAX_DAY_SHARE | MAX_TRADE_SHARE
    threshold_pct: Decimal              # e.g., 0.30
    calculation_base: str               # "total_profit" | "total_pnl"
```

### 9.3 Challenge Evaluation

```python
class PropFirmSimulator:
    """Evaluates a trade history against a PropFirmProfile."""

    def evaluate(
        self,
        profile: PropFirmProfile,
        trades: list[Trade],
        initial_balance: Decimal
    ) -> ChallengeResult:
        """
        Returns:
        - PASSED / FAILED / IN_PROGRESS
        - Breach details (which rule, when, by how much)
        - Phase completion status
        - Margin remaining before breach
        """
```

### 9.4 Configuration File Example

```toml
# config/prop_firms/ftmo.toml
[profile]
name = "FTMO Challenge"
account_sizes = [10000, 25000, 50000, 100000, 200000]

[rules]
max_overall_drawdown_pct = 0.10
drawdown_type = "static"
max_daily_loss_pct = 0.05
daily_loss_includes_floating = true
daily_reset_timezone = "Europe/Prague"

[[phases]]
name = "Phase 1 (Challenge)"
profit_target_pct = 0.10
min_trading_days = 4
max_calendar_days = 30

[[phases]]
name = "Phase 2 (Verification)"
profit_target_pct = 0.05
min_trading_days = 4
max_calendar_days = 60

[[consistency_rules]]
rule_type = "max_day_share"
threshold_pct = 0.30
calculation_base = "total_profit"
```

---

## 10. Backtesting and Validation

### 10.1 Backtesting Engine

```text
Input:
  - Trained model
  - Test dataset (out-of-sample)
  - Prop-firm profile (optional)
  - Transaction costs / spread config

Process:
  1. Replay market data bar-by-bar
  2. Feed state to model → get action
  3. Simulate order execution (spread, slippage)
  4. Update portfolio state
  5. Check risk constraints per bar
  6. Record all trades, equity curve, metrics

Output:
  - Trade list
  - Equity curve
  - Full metrics (all RiskEngine calculations)
  - PropFirmSimulator result (if profile provided)
  - Visualization data (for frontend charts)
```

### 10.2 Validation Hierarchy

```text
Level 1: In-sample training performance
Level 2: Validation set performance (HP tuning)
Level 3: Out-of-sample test performance ← minimum for consideration
Level 4: Walk-forward validation (multiple windows)
Level 5: Prop-firm simulation (with realistic constraints)
Level 6: MT5 demo forward test (live market, paper money)
```

### 10.3 Overfitting Controls

| Control | Implementation |
|---------|----------------|
| Train/Val/Test split | Temporal split, never random |
| Walk-forward testing | Rolling windows, train on past, test on future |
| Cross-validation reporting | Compare in-sample vs OOS metrics |
| Metric degradation alerts | Flag if OOS Sharpe < 50% of in-sample |
| Minimum trade count | Require N trades for statistical significance |
| Multiple timeframe testing | Strategy must work across nearby timeframes |
| Random seed reporting | Record and replay with different seeds |

---

## 11. Strategy Artifact Generation

### 11.1 Pine Script Generation

```text
Validated Strategy (Experiment + Backtest + Risk Pass)
    │
    ▼
Strategy Extractor
    │ Extracts: entry/exit logic, indicator params,
    │           risk params, position sizing
    ▼
Pine Script Template (Jinja2)
    │ Fills: indicator calculations, conditions,
    │        strategy settings, visuals
    ▼
Generated .pine file
    │ Header: experiment_id, model_version,
    │         dataset_version, backtest_hash,
    │         generation_timestamp
    ▼
Saved to strategies/pine/{experiment_id}_{version}.pine
    │
    ▼
Linked in SQLite: experiment → strategy_artifact
```

### 11.2 MQL5 Generation

Same flow as Pine Script, but:
- Template produces `.mq5` Expert Advisor or indicator
- Includes input parameters mapped from experiment hyperparameters
- Includes `#property` metadata block with traceability info

### 11.3 Traceability Requirements

Every generated script must include in comments:
- Experiment ID
- Dataset version (instrument, timeframe, date range)
- Model type and version
- Backtest summary (profit factor, Sharpe, max DD, trade count)
- Prop-firm profile used (if any)
- Generation timestamp
- Quadrium version

---

## 12. Frontend Architecture

### 12.1 Application Shell

```text
┌─────────────────────────────────────────────────┐
│  Sidebar (collapsible)  │  Main Content Area    │
│                         │                       │
│  ◉ Dashboard            │  ┌─────────────────┐  │
│  ◉ Market Data          │  │                 │  │
│  ◉ Datasets             │  │   Page Content  │  │
│  ◉ Experiments          │  │                 │  │
│  ◉ Training             │  │                 │  │
│  ◉ Backtesting          │  │                 │  │
│  ◉ Risk Analysis        │  │                 │  │
│  ◉ Prop-Firm Sim        │  │                 │  │
│  ◉ MT5 Testing          │  │                 │  │
│  ◉ Strategies           │  │                 │  │
│  ─────────────────      │  │                 │  │
│  ◉ Settings             │  │                 │  │
│  ◉ System Status        │  └─────────────────┘  │
│                         │                       │
│  [System Status Bar]    │  [Breadcrumb]         │
└─────────────────────────┴───────────────────────┘
```

### 12.2 Page Definitions

| Page | Purpose | Key Components | Primary API |
|------|---------|----------------|-------------|
| **Dashboard** | Overview of system state, recent experiments, active jobs | MetricCards, RecentExperiments, SystemHealth | `GET /api/dashboard` |
| **Market Data** | Browse/fetch/manage raw market data | InstrumentSelector, DataTable, FetchDialog | `GET/POST /api/data` |
| **Datasets** | Manage processed datasets with feature selections | DatasetList, FeatureSelector, VersionHistory | `GET/POST /api/datasets` |
| **Experiments** | Create/view/compare experiments | ExperimentTable, ExperimentDetail, CompareView | `GET/POST /api/experiments` |
| **Training** | Launch/monitor training jobs | TrainingForm, ProgressChart (WS), JobQueue | `POST /api/training`, `WS /ws/training` |
| **Backtesting** | Run/view backtests with equity curves | BacktestForm, EquityCurve, TradeTable | `POST /api/backtest` |
| **Risk Analysis** | Detailed risk metrics for any experiment | MetricsPanel, DrawdownChart, PnLDistribution | `GET /api/risk/{id}` |
| **Prop-Firm Sim** | Simulate challenge against profiles | ProfileSelector, SimulationResult, BreachTimeline | `POST /api/prop-firm/simulate` |
| **MT5 Testing** | Demo account connection and forward testing | ConnectionStatus, OrderPanel, LiveEquity (WS) | `GET/POST /api/mt5`, `WS /ws/mt5` |
| **Strategies** | Generate/manage Pine Script and MQL5 | GenerateForm, ScriptPreview, ArtifactHistory | `POST /api/strategies/generate` |
| **Settings** | System configuration, instruments, prop profiles | ConfigForms, InstrumentManager, ProfileEditor | `GET/PUT /api/config` |
| **System Status** | GPU status, DB stats, logs, MLflow link | GPUMonitor, LogViewer, ServiceHealth | `GET /api/system` |

### 12.3 Chart Library Strategy

| Chart Type | Library | Use Case |
|------------|---------|----------|
| Candlestick / OHLC | **TradingView Lightweight Charts** | Market data view, backtest visualization |
| Line / Area / Bar | **Recharts** | Equity curves, metric dashboards, P&L distribution |
| Heatmaps | **Recharts** (custom) | Correlation matrices, trade distribution |

---

## 13. API Design

### 13.1 REST Endpoints

```text
# Market Data
GET    /api/data/instruments          # List available instruments
GET    /api/data/raw                  # List raw data files
POST   /api/data/fetch                # Fetch new data from MT5/Yahoo
DELETE /api/data/raw/{id}             # Delete raw data

# Datasets
GET    /api/datasets                  # List datasets
POST   /api/datasets                  # Create processed dataset
GET    /api/datasets/{id}             # Dataset detail + metadata
GET    /api/datasets/{id}/preview     # Preview first N rows

# Experiments
GET    /api/experiments               # List experiments (filterable)
POST   /api/experiments               # Create experiment
GET    /api/experiments/{id}          # Experiment detail
PUT    /api/experiments/{id}          # Update experiment
DELETE /api/experiments/{id}          # Delete experiment
GET    /api/experiments/{id}/metrics  # Full metrics
GET    /api/experiments/compare       # Compare multiple experiments

# Training
POST   /api/training/start            # Start training job
GET    /api/training/jobs              # List active/completed jobs
POST   /api/training/stop/{job_id}    # Stop training job
GET    /api/training/{job_id}/status   # Job status

# Backtesting
POST   /api/backtest/run              # Run backtest
GET    /api/backtest/{id}             # Backtest results
GET    /api/backtest/{id}/trades      # Trade list
GET    /api/backtest/{id}/equity      # Equity curve data

# Risk
GET    /api/risk/{experiment_id}      # Risk metrics for experiment
POST   /api/risk/calculate            # Ad-hoc risk calculation

# Prop-Firm Simulation
GET    /api/prop-firm/profiles        # List profiles
POST   /api/prop-firm/profiles        # Create profile
PUT    /api/prop-firm/profiles/{id}   # Update profile
POST   /api/prop-firm/simulate        # Run simulation
GET    /api/prop-firm/simulate/{id}   # Simulation result

# MT5
GET    /api/mt5/status                # Connection status
POST   /api/mt5/connect               # Connect to MT5
POST   /api/mt5/disconnect            # Disconnect
GET    /api/mt5/account               # Account info
POST   /api/mt5/test/start            # Start demo test
POST   /api/mt5/test/stop             # Stop demo test

# Strategies
POST   /api/strategies/generate/pine  # Generate Pine Script
POST   /api/strategies/generate/mql5  # Generate MQL5
GET    /api/strategies/artifacts       # List generated scripts
GET    /api/strategies/artifacts/{id}  # Download script

# Configuration
GET    /api/config                    # Current configuration
PUT    /api/config                    # Update configuration
GET    /api/config/instruments        # Instrument config
PUT    /api/config/instruments        # Update instruments

# System
GET    /api/system/health             # Health check
GET    /api/system/gpu                # GPU/CUDA status
GET    /api/system/logs               # Recent logs
GET    /api/dashboard                 # Dashboard summary
```

### 13.2 WebSocket Channels

```text
WS /ws/training/{job_id}    # Training progress, loss curves, metrics
WS /ws/backtest/{id}        # Backtest progress
WS /ws/mt5                  # MT5 account events, position updates
WS /ws/system               # System resource usage (GPU, memory)
```

### 13.3 Response Envelope

```json
{
  "success": true,
  "data": { ... },
  "error": null,
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total": 142
  }
}
```

---

## 14. Configuration

### 14.1 Configuration Hierarchy

```text
1. config/default.toml        ← Base defaults
2. config/*.toml               ← Feature-specific configs
3. .env                        ← Secrets and environment overrides
4. CLI arguments               ← Runtime overrides
```

### 14.2 Key Configuration Areas

| Area | File | Format | Contents |
|------|------|--------|----------|
| App defaults | `config/default.toml` | TOML | API port, log level, data paths |
| Instruments | `config/instruments.toml` | TOML | Symbol names, lot sizes, pip values |
| Timeframes | `config/timeframes.toml` | TOML | M1, M5, M15, H1, H4, D1 definitions |
| Prop firms | `config/prop_firms/*.toml` | TOML | Per-firm rule profiles |
| MT5 credentials | `.env` | Env vars | `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` |
| ML defaults | `config/default.toml` | TOML | Default batch size, learning rate, etc. |
| GPU config | `config/default.toml` | TOML | CUDA device, mixed precision, workers |

### 14.3 .env Template

```env
# MT5 Configuration (NEVER commit real values)
MT5_LOGIN=
MT5_PASSWORD=
MT5_SERVER=
MT5_PATH="C:\\Program Files\\MetaTrader 5\\terminal64.exe"
MT5_ACCOUNT_TYPE=demo

# Application
QUADRIUM_ENV=development
QUADRIUM_LOG_LEVEL=INFO
QUADRIUM_API_PORT=8000

# CUDA
CUDA_VISIBLE_DEVICES=0
```

---

## 15. Testing Strategy

### 15.1 Test Categories

| Category | Framework | Target Coverage | Priority |
|----------|-----------|-----------------|----------|
| **Risk engine unit tests** | pytest | **100%** | **Critical** |
| **Prop-firm simulator tests** | pytest | **100%** | **Critical** |
| **Financial calculation tests** | pytest | **100%** | **Critical** |
| Backend service tests | pytest | 80%+ | High |
| API endpoint tests | pytest + httpx | 80%+ | High |
| Data pipeline tests | pytest | 80%+ | High |
| ML pipeline tests | pytest | 70%+ | Medium |
| Frontend component tests | Vitest | 60%+ | Medium |
| E2E tests | Playwright | Critical paths | Medium |
| MT5 integration tests | pytest (mocked) | Connection/order flow | Medium |

### 15.2 Critical Test Cases (Risk Engine)

```python
# These tests are NON-NEGOTIABLE before any production use

class TestMaxDrawdown:
    def test_simple_drawdown(self): ...
    def test_no_drawdown_monotonic_increase(self): ...
    def test_drawdown_at_beginning(self): ...
    def test_drawdown_at_end(self): ...
    def test_multiple_drawdowns_returns_max(self): ...
    def test_trailing_drawdown(self): ...
    def test_static_vs_trailing_difference(self): ...

class TestDailyLoss:
    def test_single_day_loss(self): ...
    def test_timezone_day_boundary(self): ...
    def test_floating_loss_included(self): ...
    def test_floating_loss_excluded(self): ...
    def test_daily_reset_at_midnight_server_time(self): ...
    def test_worst_daily_loss(self): ...

class TestPropFirmSimulation:
    def test_challenge_pass(self): ...
    def test_drawdown_breach_fails(self): ...
    def test_daily_loss_breach_fails(self): ...
    def test_profit_target_reached(self): ...
    def test_consistency_rule_violation(self): ...
    def test_min_trading_days_not_met(self): ...
    def test_multiple_phases(self): ...
    def test_edge_case_exactly_at_limit(self): ...
```

### 15.3 Test Data

- Synthetic trade generators for deterministic test cases
- Known-good sample datasets (XAUUSD H1, small date range)
- Edge-case equity curves (flash crash, gap, flat periods)

---

## 16. Logging and Observability

### 16.1 Logging Architecture

| Log Category | Destination | Format | Retention |
|--------------|-------------|--------|-----------|
| Application logs | `logs/app.log` | Structured JSON (structlog) | 30 days |
| Training logs | `logs/training/{job_id}.log` | Structured JSON | Permanent |
| Backtest logs | `logs/backtest/{id}.log` | Structured JSON | Permanent |
| MT5 events | `logs/mt5.log` | Structured JSON | 90 days |
| API access | `logs/access.log` | JSON | 7 days |

### 16.2 Key Observability Points

| Metric | Source | Exposed Via |
|--------|--------|-------------|
| GPU utilization | `nvidia-smi` / `torch.cuda` | `GET /api/system/gpu` |
| Training loss curve | Training callback | `WS /ws/training/{id}` |
| Memory usage | `psutil` | `GET /api/system/health` |
| DB sizes | File system | `GET /api/system/health` |
| Active jobs | SQLite job table | `GET /api/training/jobs` |
| MT5 connection status | MT5 health check | `GET /api/mt5/status` |

---

## 17. Development Phases

### Phase 0: Repository and Architecture
- [x] Inspect existing repository
- [x] Analyze architecture requirements
- [x] Create Implementation.md
- [x] User review and approval (Completed)

### Phase 1: Project Scaffolding
- Reorganize repo structure (move `src/` → `frontend/src/`)
- Initialize Python backend (`backend/` with `pyproject.toml`)
- Set up `uv` environment with core dependencies
- Create `.env.example` and config structure
- Extend `.gitignore` for Python + data artifacts
- Verify CUDA/GPU availability (`scripts/verify_gpu.py`)
- Set up pytest and basic test structure

### Phase 2: Core Backend
- FastAPI app factory with health check
- SQLite database schema + models (Pydantic + SQLAlchemy)
- DuckDB analytics database initialization
- Configuration loading (TOML + .env)
- Structured logging (structlog)
- API response envelope
- Basic REST endpoint scaffolding

### Phase 3: Data Pipeline
- MT5 data fetcher service
- Yahoo Finance fallback fetcher
- Raw data storage (Parquet)
- Data cleaning pipeline
- DuckDB catalog management
- Dataset creation + versioning
- API endpoints for data management

### Phase 4: Feature Engineering
- TA-Lib indicator calculations
- Custom feature generators
- Feature selection interface
- Processed dataset storage (Parquet)
- API endpoints for feature management

### Phase 5: ML/FinRL Integration
- FinRL environment setup
- Custom `QuadriumTradingEnv`
- Agent factory (PPO, SAC, A2C, DDPG, TD3)
- Training pipeline with GPU support
- MLflow experiment tracking
- Model persistence (`.pt` + metadata)
- Training WebSocket progress reporting
- API endpoints for training management

### Phase 6: Backtesting Engine
- Bar-by-bar replay engine
- Transaction cost simulation
- Trade recording
- Equity curve generation
- Metric calculation integration
- Backtest result storage (DuckDB)
- API endpoints for backtesting

### Phase 7: Risk Engine
- Implement all risk calculations (Section 9.1)
- 100% test coverage for risk calculations
- API endpoints for risk analysis

### Phase 8: Prop-Firm Simulator
- Profile configuration loading (TOML)
- Challenge evaluation engine
- Multi-phase support
- Consistency rule evaluation
- 100% test coverage
- API endpoints for simulation

### Phase 9: Frontend Application
- Application shell (sidebar, router, layout)
- Dashboard page
- Market Data page
- Dataset management page
- Experiment management page
- Training page (with WebSocket progress)
- Backtest visualization page
- Risk analysis page
- Prop-firm simulation page
- Settings page
- System status page

### Phase 10: MT5 Demo Integration
- MT5 connection management
- Demo account forward testing
- Trade event capture
- Position monitoring WebSocket
- API endpoints for MT5

### Phase 11: Strategy Generation
- Pine Script Jinja2 templates
- MQL5 Jinja2 templates
- Strategy extraction from experiments
- Traceability metadata injection
- Generation API endpoints
- Strategy management page

### Phase 12: Hardening
- Complete test coverage targets
- E2E tests for critical flows
- Error handling audit
- Security review (credentials, input validation)
- Performance optimization
- Documentation

---

## 18. MVP Definition

### Must Have (MVP)
- [ ] Data ingestion from MT5 (XAUUSD, at minimum)
- [ ] Data cleaning and storage (Parquet + DuckDB catalog)
- [ ] Basic feature engineering (common TA indicators)
- [ ] One RL agent training (PPO via FinRL)
- [ ] GPU-accelerated training
- [ ] Backtesting with trade recording
- [ ] Core risk metrics (drawdown, daily loss, Sharpe, profit factor)
- [ ] Prop-firm simulation with one configurable profile
- [ ] Experiment tracking (SQLite + MLflow)
- [ ] Frontend: Dashboard, Data, Experiments, Training, Backtest, Risk pages
- [ ] REST API with OpenAPI docs
- [ ] WebSocket for training progress

### Should Have
- [ ] Multiple RL algorithms (SAC, A2C, TD3)
- [ ] Walk-forward validation
- [ ] Experiment comparison view
- [ ] Multiple prop-firm profiles
- [ ] MT5 demo forward testing
- [ ] Pine Script generation
- [ ] Full frontend for all pages
- [ ] Optuna hyperparameter tuning

### Optional (Post-MVP)
- [ ] MQL5 generation
- [ ] Yahoo Finance fallback data source
- [ ] Crypto instrument support
- [ ] Custom reward function builder
- [ ] Ensemble strategies
- [ ] Advanced chart annotations
- [ ] Export reports (PDF/HTML)

### Future
- [ ] Live trading capability (gated, explicit opt-in)
- [ ] FinRL-Trading (FinRL-X) migration
- [ ] LLM-assisted strategy analysis
- [ ] Multi-GPU support
- [ ] Additional data sources

---

## 19. Risks and Technical Unknowns

### High Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **RTX 3050 VRAM insufficient for complex RL models** | Training fails or is impractically slow | Mixed precision, small batch sizes, CPU replay buffers. Profile VRAM early in Phase 5. If 4GB laptop variant, may need aggressive model simplification. |
| **FinRL environment compatibility with Forex/Metals** | FinRL's built-in envs are stock-focused | Custom `QuadriumTradingEnv` that extends Gymnasium. May need significant customization for Forex lot sizing, pip values, spread mechanics. |
| **MT5 Python library reliability on Windows** | Connection drops, API quirks | Circuit breaker, comprehensive error handling, dedicated thread pool. Test extensively in Phase 10. |
| **Prop-firm rule edge cases** | Incorrect breach detection → false confidence | 100% test coverage with real-world edge cases. Verify against known challenge results if possible. |

### Medium Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **DuckDB concurrent access limitations** | Potential write conflicts if multiple operations run simultaneously | Single-writer pattern. Analytical reads are concurrent-safe. SQLite handles transactional writes. |
| **FinRL API changes** | Breaking changes in FinRL library | Pin FinRL version. Wrap all FinRL calls in adapter layer. |
| **Overfitting in RL strategies** | Strategies that backtest well but fail live | Walk-forward validation, OOS testing, minimum trade counts, random seed variation. |
| **Pine Script / MQL5 template complexity** | Generated scripts may not capture all strategy nuances | Start with simple indicator-based strategies. Complex RL strategies may require manual translation. |

### Low Risk

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Frontend build tool changes** | Vite 8 is very new | Vite has stable API. Already working. |
| **Python dependency conflicts** | FinRL + PyTorch + MT5 version conflicts | Use `uv` with pinned versions. Test environment setup script. |

---

## 20. Immediate Next Steps

After this document is approved:

1. **Phase 1: Project Scaffolding** — Reorganize the repository, create the Python backend skeleton, verify GPU/CUDA availability, set up test infrastructure.

2. **GPU Verification** — Run `scripts/verify_gpu.py` to confirm CUDA availability, VRAM size, and PyTorch GPU access. This determines whether the RTX 3050's VRAM is 4GB, 6GB, or 8GB, which directly impacts ML training configuration.

3. **Phase 2: Core Backend** — Stand up the FastAPI server with health checks, database schemas, and basic API scaffolding. This creates the foundation everything else builds on.

The implementation order will proceed with backend and frontend development **in parallel**:
```text
Backend Stream:  Scaffolding → Backend → Data Pipeline → Features → ML/Training → Backtesting → Risk Engine → Prop-Firm
Frontend Stream: Scaffolding → UI Shell → Data Views → Dashboard → Training Views → Backtest Visualizations
```

Each phase produces a working, testable increment. The MVP target includes Phases 1–9 (excluding MT5 live testing and script generation, which are "Should Have").

---

> [!NOTE]
> **User Review Completed (2026-09-23)**
> - **GPU:** Confirmed Laptop (4GB) variant.
> - **Structure:** Monorepo approved.
> - **Database:** DuckDB + SQLite dual-database approved.
> - **Backend:** FastAPI approved.
> - **Phasing:** Frontend UI development will happen in parallel with backend development.

