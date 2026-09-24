# Quadrium Architecture

Quadrium is designed to handle both rapid transactional state updates and heavy analytical queries over large market datasets and backtest results.

## Database Split (SQLite vs. DuckDB)

Quadrium uses a dual-database approach to balance these needs:

1. **SQLite (OLTP)**: Manages application state. It stores active experiments, training/backtest jobs, prop firm profiles, and system settings. This database provides ACID guarantees for fast, transactional updates.
2. **DuckDB (OLAP)**: Powers the analytical engine. It handles high-volume data such as raw market ticks, processed ML datasets, and individual backtest trades/equity curves. DuckDB's columnar format allows fast aggregations and metric calculations (e.g. max drawdown, Sharpe ratio).

## Job Lifecycle

The system delegates heavy computations to background tasks:
1. **Fetch**: Data is fetched from sources like MT5 or yfinance and stored as Parquet, with metadata registered in DuckDB.
2. **Dataset**: Raw data is enriched with technical features and saved as a new version.
3. **Train**: RL agents (via FinRL/Stable-Baselines3) are trained on the datasets. Progress is logged to MLflow and job state is tracked in SQLite.
4. **Backtest**: Trained models generate trading decisions over historical data. The backtest engine executes the logic, saving equity curves and trades into DuckDB.
5. **Prop Firm Sim**: The backtest trades are evaluated against structured prop firm rules (drawdown limits, consistency rules) to simulate challenge passes/fails.

## Generated Strategies

Once a model proves profitable in backtesting, it can be exported to target platforms:
- **`strategies/pine`**: Pine Script v5 for TradingView alerts and manual review.
- **`strategies/mql5`**: MQL5 Expert Advisors (EAs) for automated execution on MetaTrader 5.
These artifacts are generated from the trained model's decision logic and stored for deployment.
