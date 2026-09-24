# Quadrium

Quadrium is a local-first AI/ML forex trading research platform. It features a FastAPI backend and a Vite/React frontend for RL training via Stable-Baselines3/FinRL, MT5 + yfinance data ingestion, DuckDB analytics, prop-firm challenge simulation, and Pine/MQL5 strategy export.

## Architecture

- **Backend**: FastAPI, SQLite (transactional state), DuckDB (analytics), PyTorch, FinRL.
- **Frontend**: Vite, React, TypeScript.
- **Storage**: Local filesystem for datasets, models, and MLflow runs.

## Prerequisites

- Python 3.12
- Node.js 20+
- (Optional) CUDA-compatible GPU for accelerated training
- (Optional) MetaTrader 5 on Windows for MT5 data ingestion

## Setup

### Backend

1. Navigate to `backend/`.
2. Install dependencies using `uv` (recommended) or `pip`:
   ```bash
   uv sync --all-extras
   ```
3. Copy `.env.example` to `.env` in the root directory and configure settings.
4. Run the backend server:
   ```bash
   uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

### Frontend

1. Navigate to `frontend/`.
2. Install dependencies:
   ```bash
   npm install
   ```
3. Copy `.env.example` (if exists) or create `.env` and set `VITE_API_BASE_URL=http://127.0.0.1:8000/api`.
4. Run the frontend dev server:
   ```bash
   npm run dev
   ```

The frontend will be available at `http://localhost:5173`.
