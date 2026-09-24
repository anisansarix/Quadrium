# Quadrium

> An AI-First Quantitative Trading & Reinforcement Learning Execution Platform

Quadrium is a local-first, end-to-end framework built for algorithmic traders and AI researchers. It provides a complete pipeline for ingesting historical data, training Deep Reinforcement Learning models (like PPO, SAC), and seamlessly deploying those models directly to MetaTrader 5 (MT5) for live execution.

## ?? Features

- **End-to-End Pipeline**: From raw tick data to live MT5 execution.
- **Reinforcement Learning Engine**: Native support for Stable-Baselines3 (PPO, SAC, A2C, TD3, DDPG) through custom \QuadriumTradingEnv\ environments.
- **Crash-Resilient State Recovery**: Live engine automatically synchronizes with MT5 positions upon boot to prevent duplicate or hedged trades after power loss or server restarts.
- **Live Agent Telemetry**: Beautiful React dashboard for monitoring your RL Agent's internal confidence state (Agent Brain), P/L, Margin, and Drawdown in real-time.
- **Robust Risk Management**: Fully integrated prop-firm drawdown rules (trailing, static, equity-based) directly into the agent's reward functions and live executor.
- **Local-First Architecture**: Powered by FastAPI, SQLite, DuckDB, and PyTorch. No cloud dependencies; run completely offline and keep your IP safe.

## ?? Tech Stack

- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, shadcn/ui, Recharts.
- **Backend**: FastAPI, Python 3.10+, SQLAlchemy, Pydantic.
- **ML / Data**: PyTorch, Stable-Baselines3, Pandas, DuckDB.
- **Execution**: MetaTrader5 Python API.

## ?? Project Structure

\\\	ext
quadrium/
+-- backend/
¦   +-- app/
¦   ¦   +-- api/          # FastAPI Routes (Live Trading, MT5, Experiments, Risk)
¦   ¦   +-- core/         # Config & DB setup (SQLite + DuckDB)
¦   ¦   +-- ml/           # RL Environments (QuadriumTradingEnv) & AgentFactory
¦   ¦   +-- models/       # DB Schemas & Pydantic models
¦   ¦   +-- services/     # Core Business Logic & MT5 Execution Engine
¦   +-- main.py           # FastAPI Entrypoint
+-- frontend/
¦   +-- src/
¦   ¦   +-- api/          # React Query API Hooks
¦   ¦   +-- components/   # shadcn UI components & Sidebar
¦   ¦   +-- pages/        # Dashboard, Risk, Models, Backtest UI
¦   ¦   +-- App.tsx       # Routing
¦   +-- vite.config.ts    # Vite Config
+-- config/               # TOML configs (quadrium.toml, prop_firms.toml)
+-- scripts/              # Output directory for generated Pine/MQL5 scripts
+-- data/                 # Local SQLite/DuckDB database files
+-- models/               # Extracted Stable-Baselines3 .zip models
\\\

## ?? Quick Start

### 1. Prerequisites
- Python 3.10+
- Node.js 18+
- MetaTrader 5 Terminal installed locally
- A trained Stable-Baselines3 model (Optional, but required for live trading)

### 2. Setup
Clone the repository and run the setup scripts (if available), or manually install dependencies:

**Backend:**
\\\ash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
\\\

**Frontend:**
\\\ash
cd frontend
npm install
\\\

### 3. Importing Your Custom RL Model
Quadrium allows you to bring your own pre-trained models. To import your Stable-Baselines3 model:
1. Zip your model files (\data\, \policy.pth\, \system_info.txt\, etc.) into a file named \model.zip\.
2. Place it in \models/<your_model_name>/\.
3. Select it from the **Agent Brain** dropdown in the Dashboard.

### 4. Running the Platform
For Windows users, simply double-click the included \start_servers.bat\ file from the root directory to automatically launch both the FastAPI backend and the Vite frontend.

Alternatively, run them manually:
\\\ash
# Backend (Terminal 1)
cd backend && uvicorn app.main:app --reload

# Frontend (Terminal 2)
cd frontend && npm run dev
\\\

Open [http://localhost:5173](http://localhost:5173) in your browser.

## ?? Disclaimer
This software is for educational and research purposes only. Do not risk money which you are afraid to lose. USE THE SOFTWARE AT YOUR OWN RISK. THE AUTHORS AND ALL AFFILIATES ASSUME NO RESPONSIBILITY FOR YOUR TRADING RESULTS.

## ?? License
MIT License
