# Quadrium — Code Review: Improvements & Fixes

Reviewed repo: `anisansarix/Quadrium` (5 commits, monorepo: FastAPI backend + Vite/React
frontend for a local-first AI/ML forex trading research platform — RL training via
Stable-Baselines3/FinRL, MT5 + yfinance data ingestion, DuckDB analytics, prop-firm
challenge simulation, Pine/MQL5 strategy export).

The project has a genuinely thoughtful architecture (SQLite for OLTP + DuckDB for
analytics, typed settings, structured logging, fetcher abstraction with async
offloading). However, in its current state **the backend cannot start and no test can
be collected**, on top of several correctness, security, and quality gaps. Items are
ordered by severity.

---

## 1. Blocking / Critical

### 1.1 `app/models` package does not exist — the app cannot import

`app/core/database.py`, every router in `app/api/*`, `app/services/prop_firm.py`, and
`tests/backend/conftest.py` all import from `app.models.db`, `app.models.schemas`, or
`app.models.enums`:

```python
from app.models.db import Base                                   # core/database.py
from app.models.schemas import APIResponse, GPUStatus, HealthResponse  # api/system.py
from app.models.enums import ChallengeResult, ConsistencyType, DrawdownType  # services/prop_firm.py
```

There is no `backend/app/models/` directory anywhere in the repo (confirmed against
git history and `.gitignore` — it isn't an ignored/build artifact, it was simply never
committed). As a result:

- `uvicorn app.main:app` fails immediately on startup (`init_sqlite()` imports
  `app.models.db.Base`).
- **Every** file in `tests/backend/unit/` fails at collection because
  `tests/backend/conftest.py` imports `app.models.db` at module scope.

**Fix:** add `backend/app/models/__init__.py`, `db.py` (SQLAlchemy `Base` +
`Experiment` and any other ORM models used by `api/experiments.py`), `schemas.py`
(`APIResponse[T]`, `GPUStatus`, `HealthResponse`, and the request/response schemas
referenced by `api/data.py`), and `enums.py` (`ChallengeResult`, `ConsistencyType`,
`DrawdownType`). This is the single highest-priority fix — nothing else can be
verified to work until it exists.

### 1.2 `MT5Service` import is unguarded — app can't start off Windows

`backend/app/services/mt5_service.py`:

```python
import MetaTrader5 as mt5   # top-level, no try/except
```

`MetaTrader5` is Windows-only and is correctly declared as an **optional** extra in
`pyproject.toml` (`[project.optional-dependencies] mt5 = [...]`). `app/api/mt5.py`
imports `MT5Service` unconditionally, and `app/api/router.py` unconditionally includes
the MT5 router — so on Linux/macOS, or Windows without `pip install -e ".[mt5]"`, the
whole application fails at import time with `ModuleNotFoundError`.

Contrast this with `app/services/fetchers/mt5_fetcher.py`, which does it correctly:

```python
try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None
```

**Fix:** apply the same guard to `mt5_service.py`, and gate router registration (or
raise a clean 503 from the endpoints) on `settings.mt5.enabled` / import success rather
than crashing the whole process. The `MT5Settings.enabled` flag already exists in
config but is currently **never read anywhere** in the codebase — wire it up.

### 1.3 `config/default.toml` is loaded but never applied

`app/config.py`:

```python
def load_settings() -> Settings:
    config_path = _PROJECT_ROOT / "config" / "default.toml"
    _toml_defaults = _load_toml(config_path)   # loaded...
    # Pydantic settings reads from env vars and .env file
    return Settings()                          # ...and discarded
```

The TOML file is parsed into `_toml_defaults` and then never merged into `Settings()`
(the comment even says "future: merge TOML values into Settings"). Every value in
`config/default.toml` — GPU settings, training defaults, backtest spread/commission/
slippage — currently has **zero effect**. A user editing that file to tune training or
backtest behavior will see no change and won't know why.

**Fix:** either pass `_toml_defaults` into `Settings(**_toml_defaults)` (with proper
nested-key handling), or remove `config/default.toml` and the misleading loader code
until the merge is implemented, so the config surface matches reality.

### 1.4 `.env.example` documents env vars that don't work

`.env.example` lists `QUADRIUM_API_HOST` and `QUADRIUM_API_PORT`, but `APISettings`
(and `DatabaseSettings`, `GPUSettings`, `TrainingSettings`) declare no `env_prefix`,
and the parent `Settings.model_config` sets no `env_nested_delimiter`. Only
`MT5Settings` works from env vars, because it explicitly sets its own
`env_prefix="MT5_"`. Setting `QUADRIUM_API_HOST=0.0.0.0` today silently does nothing.

**Fix:** add `env_nested_delimiter="__"` to `Settings.model_config` and update
`.env.example` to the real variable names (`QUADRIUM_API__HOST`,
`QUADRIUM_API__PORT`, etc.), or give each sub-settings class its own `env_prefix` like
`MT5Settings` already does.

---

## 2. High-severity functional & architectural issues

### 2.1 Job state lives in a plain in-process dict

`app/api/training.py` and `app/api/backtest.py` both track background jobs in a bare
module-level `dict` (`_active_jobs`, `_active_backtests`). The code's own comment
acknowledges this: `# In-memory store for tracking jobs (in production, use SQLite job
table)`. Consequences: job history is lost on every reload/restart, it's not safe with
multiple uvicorn workers, and it grows unbounded for the life of the process.

**Fix:** persist jobs in the existing SQLite database (a `Job`/`TrainingRun` table via
the ORM models from 1.1) instead of a process dict.

### 2.2 No concurrency/resource control on training & backtest jobs

`BackgroundTasks` runs jobs in-process with no queue, no limit on concurrent jobs, and
no GPU-memory guard. The project's own settings are explicitly tuned for a 4 GB VRAM
GPU (`GPUSettings` docstring: _"tuned for RTX 3050 Laptop (4GB VRAM)"_), yet nothing
stops two `/training/start` calls from running simultaneously and exhausting VRAM or
starving the same thread pool FastAPI uses for every other request.

**Fix:** cap concurrent training/backtest jobs (e.g. a semaphore or a real task queue
such as Celery/RQ/`arq`), and surface a clear "busy" response when at capacity.

### 2.3 `Trainer.train()` hardcodes CUDA autocast, breaking CPU-only training

`app/ml/training/trainer.py`:

```python
with torch.amp.autocast("cuda"):
    agent.learn(total_timesteps=total_timesteps, callback=callback)
```

`AgentFactory.create_agent` correctly falls back to `device = "cpu"` when no GPU is
present, but `Trainer.train()` unconditionally requests CUDA autocast. On any
CPU-only machine this raises at training start, and mixed precision on CPU isn't even
meaningful.

**Fix:** branch on `torch.cuda.is_available()` (or the agent's own `.device`) before
wrapping in `torch.amp.autocast("cuda", enabled=...)`, or use
`torch.autocast(device_type=agent.device, enabled=torch.cuda.is_available())`.

### 2.4 Placeholder endpoints return HTTP 200 with fake "success" bodies

- `GET /api/risk/{experiment_id}` returns
  `{"success": true, "data": {"metrics": "Not fully implemented until Backtest integration"}}`.
- `POST /api/prop-firm/simulate` returns
  `{"success": true, "data": {"status": "in_progress", "detail": "Integration with backtest trades pending."}}`
  without running any simulation.

A frontend (or any API consumer) parsing `success: true` has no way to tell these
apart from real results.

**Fix:** either implement them (both already have the underlying `RiskEngine` /
`PropFirmSimulator` code needed — they just aren't wired to real trade data yet), or
have them return `501 Not Implemented` / `success: false` until they are.

### 2.5 `Decimal` usage in the risk/backtest engines is cosmetic only

`RiskEngine` and `BacktestEngine` type all monetary fields as `Decimal`, but nearly
every calculation does `float(t.pnl)` first and re-wraps the result as
`Decimal(str(result))` at the end (e.g. `profit_factor`, `expectancy`,
`max_drawdown`, `sharpe_ratio`'s callers). This gives the appearance of
decimal-precision money math while all real arithmetic happens in binary floating
point — the exact rounding error `Decimal` is normally used to avoid.

**Fix:** either commit to `Decimal` arithmetic throughout (using `decimal` module ops,
not `float()` round-trips), or drop `Decimal` in favor of `float`/`numpy` with a
documented tolerance — the current hybrid gives neither correctness nor performance.

### 2.6 Mislabeled / incomplete risk metrics

- `RiskEngine.average_r()` is documented as "R-multiple" but actually computes
  `avg(win) / avg(loss)` — a different, unrelated ratio (real R-multiple needs the
  planned risk per trade, e.g. stop-loss distance, which isn't tracked anywhere).
- `RiskEngine.consistency_score()` hardcodes `max_trade_share=Decimal('0')` with a
  comment `# Requires trade list to compute` — the field exists in the result and is
  presumably surfaced to users evaluating prop-firm consistency rules, but it is never
  actually computed.

**Fix:** rename `average_r` to reflect what it computes (e.g. `win_loss_ratio`) or
implement true R-multiples once stop-loss data is tracked per trade; implement
`max_trade_share` or remove the field until it's implemented.

---

## 3. Security

### 3.1 No authentication on any endpoint

Every route under `/api/*` — including `/mt5/connect` (which accepts MT5 login
credentials), `/training/start`, and `/data/fetch` — is open to any caller that can
reach the port. Even for a "local-first" desktop tool this is worth hardening,
especially since CORS is configured with `allow_credentials=True` alongside
`allow_methods=["*"]` and `allow_headers=["*"]`.

**Fix:** at minimum, confirm the server only ever binds to `127.0.0.1` (it does, by
default) and never becomes reachable on `0.0.0.0` without an auth layer; consider a
simple local bearer token for defense-in-depth once the app is exposed beyond a single
user's machine.

### 3.2 MT5 credentials are plain `str`, not `SecretStr`

`MT5Settings.login` / `.password` in `config.py`, and `ConnectRequest.password` in
`api/mt5.py`, are typed as plain `str`. They can end up in `repr()`/log output (e.g. if
a future log statement does `logger.info("connect", request=request)`,
`structlog`/`pydantic` will happily serialize the password). `mt5_service.py` also uses
raw `print()` for errors, which won't go through any log redaction path.

**Fix:** use `pydantic.SecretStr` for `login`/`password` fields so they render as
`**********` by default, and route all MT5 status/error output through the app's
`structlog` logger (see 4.2) rather than `print()`.

### 3.3 Unvalidated `symbol`/`timeframe` used to build filesystem paths

`DataService.fetch_and_store` (`app/services/data_service.py`) builds a directory
directly from user input with no allow-list:

```python
raw_dir = settings.resolve_path(settings.data_raw_dir) / symbol.upper() / timeframe.upper()
```

`FetchDataRequest.symbol` is an unconstrained `str`. A value like `"../../../etc"`
would resolve outside `data/raw/`, and the same pattern is repeated for `timeframe`.

**Fix:** validate `symbol`/`timeframe` against a strict pattern (e.g.
`^[A-Za-z0-9._-]{1,20}$`) or an allow-list drawn from `config/instruments.toml` /
`config/timeframes.toml`, which already exist in the repo for exactly this purpose but
aren't currently consulted at the API boundary.

### 3.4 Raw exception text returned to API clients

`app/api/data.py`:

```python
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")
```

This pattern (repeated elsewhere) leaks internal exception text — potentially file
paths, library internals, or stack details — directly to the HTTP response.

**Fix:** log the full exception server-side (`log.error(..., error=str(e))`, already
done in some routers — apply consistently) and return a generic
`"Internal server error"` message to the client, matching the better pattern already
used in `api/datasets.py`.

---

## 4. Consistency & code quality

### 4.1 Root `README.md` is completely empty (0 bytes)

There is no top-level description of what Quadrium is, how the pieces (backend,
frontend, config, strategies) fit together, or how to run the whole stack.
`backend/README.md` exists but is minimal and Windows-only
(`.venv\Scripts\activate`), and there's no top-level setup doc that covers the
frontend, `.env` setup, or the data/models/mlruns directories the app expects to
exist.

**Fix:** write a root `README.md` covering: architecture overview, prerequisites
(Python 3.12, Node, optional CUDA/MT5), `backend/` + `frontend/` setup for both
Windows and Linux/macOS, and how the two halves talk to each other (`VITE` dev
server → FastAPI on `127.0.0.1:8000`).

### 4.2 `MT5Service` uses `print()` instead of the project's logger

Every other module uses `structlog` via `get_logger(__name__)`; `mt5_service.py` alone
uses raw `print()` calls for errors, which won't appear in structured/JSON logs in
production mode (`settings.env != "development"`).

**Fix:** switch to `get_logger(__name__)` for consistency, and see 3.2 for why
this also matters for credential redaction.

### 4.3 MT5 resilience settings are defined but unused

`MT5Settings` declares `retry_attempts`, `retry_delay_seconds`,
`circuit_breaker_threshold`, and `circuit_breaker_recovery_seconds`, but neither
`MT5Service` nor `MT5Fetcher` reference any of them — there is no retry loop and no
circuit breaker anywhere in the code. A flaky MT5 terminal connection will simply fail
once with no backoff.

**Fix:** implement retry/circuit-breaker logic in `MT5Fetcher`/`MT5Service` using the
existing settings, or remove the settings until they're backed by real behavior.

### 4.4 Inconsistent API response envelopes

`api/system.py` and `api/data.py` use a typed `APIResponse[T]` Pydantic model, while
`api/datasets.py`, `api/training.py`, `api/backtest.py`, `api/risk.py`, and
`api/prop_firm.py` hand-build `{"success": True, "data": ..., "error": None}` dict
literals. Both shapes look identical on the wire today, but only one is actually
validated/typed, and future field changes will only be enforced in one of the two
paths.

**Fix:** route every endpoint through the shared `APIResponse[T]` model once it exists
in `app/models/schemas.py`.

### 4.5 yfinance fetcher silently can't serve H4 data

`YFinanceFetcher.TIMEFRAME_MAP` has no entry for `H4` (comment: _"Yfinance doesn't
natively support 4h"_), so a `/data/fetch` call with `timeframe="H4", source="yfinance"`
raises `ValueError` with no fallback, even though `config/timeframes.toml` presumably
lists H4 as a supported timeframe for the platform generally.

**Fix:** either resample from `H1` to `H4` client-side in `YFinanceFetcher`, or have
`DataService` reject that combination with a clearer, source-specific error message
up front (e.g. "H4 is only available via the MT5 source").

### 4.6 Frontend API base URL is hardcoded

`frontend/src/api/client.ts`:

```ts
export const apiClient = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
  ...
});
```

This can't be changed without editing source, so pointing the frontend at a different
port/host (or a packaged desktop build) requires a code change.

**Fix:** read from a Vite env var, e.g. `import.meta.env.VITE_API_BASE_URL ??
'http://127.0.0.1:8000/api'`, and document it in a frontend `.env.example`.

---

## 5. Testing & CI gaps

### 5.1 No test in the repo currently runs

Because of 1.1, `tests/backend/conftest.py` fails at import/collection time, so
`pytest` cannot run a single test in `tests/backend/unit/` (which otherwise looks
reasonably thorough — risk engine, prop-firm, data/dataset/feature services, FinRL
agents, and the forex env all have dedicated test files).

**Fix:** priority #1 (fix 1.1) directly unblocks this whole suite — re-run it after
adding `app/models` and confirm it's green before merging further changes.

### 5.2 Frontend has no test coverage or test runner

`tests/frontend/unit/` and `tests/frontend/e2e/` contain nothing but `.gitkeep`
placeholders, and `frontend/package.json` has no test dependency (`vitest`,
`@testing-library/react`, `playwright`, etc.) or `test` script at all.

**Fix:** add `vitest` + `@testing-library/react` for component/hook tests (the
`useSystemHealth`/`useDatasets`/etc. hooks in `api/hooks.ts` are good starting
candidates), and consider Playwright for a smoke-level e2e test of the dashboard
against a running backend.

### 5.3 No CI workflow

There is no `.github/workflows/*` (or equivalent) in the repo, despite `ruff`,
`mypy --strict`, and `pytest` all being configured in `backend/pyproject.toml`. None
of these currently run automatically on push/PR.

**Fix:** add a GitHub Actions workflow that, at minimum: installs backend deps, runs
`ruff check`, `mypy`, and `pytest`; and separately runs `npm ci && npm run lint &&
npm run build` for the frontend.

### 5.4 `docs/` is empty

The `docs/` folder contains only a `.gitkeep`. Given the project spans data
ingestion, RL training, backtesting, risk metrics, and prop-firm simulation, an
architecture doc (even a short one) would materially help onboarding.

**Fix:** add at least one `docs/architecture.md` explaining the SQLite-vs-DuckDB
split, the job lifecycle (fetch → dataset → train → backtest → prop-firm sim), and
where generated strategies (`strategies/pine`, `strategies/mql5`) fit in.

---

## Suggested order of work

1. **Unblock the app**: add `app/models/{db,schemas,enums}.py` (1.1), guard the MT5
   import (1.2), fix env/TOML config wiring (1.3, 1.4).
2. **Get tests green**: re-run `pytest` after step 1 (5.1), add a CI workflow (5.3).
3. **Persist job state to SQLite** (2.1) and add a concurrency cap (2.2) before this
   is used for real GPU training runs.
4. **Security pass**: `SecretStr` for MT5 creds (3.2), input validation on
   symbol/timeframe (3.3), stop leaking exception text (3.4).
5. **Finish or clearly stub** the placeholder risk/prop-firm endpoints (2.4) and fix
   the CPU-autocast crash (2.3) before relying on training on non-GPU machines.
6. **Docs & consistency cleanup**: root README (4.1), response-envelope consistency
   (4.4), frontend test scaffolding (5.2).
