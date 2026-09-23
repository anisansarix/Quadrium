import asyncio
import pandas as pd
import numpy as np
from datetime import datetime
from decimal import Decimal

from app.core.database import init_sqlite, get_duckdb, close_sqlite, close_duckdb
from app.ml.training.trainer import Trainer
from app.services.backtest_engine import BacktestEngine
from app.services.prop_firm import PropFirmSimulator, PropFirmProfile, DrawdownType, ChallengePhase
from app.config import settings

def create_sample_data(rows: int = 1000) -> pd.DataFrame:
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", periods=rows, freq="h")
    df = pd.DataFrame({
        "time": dates,
        "open": np.random.uniform(100.0, 105.0, rows),
        "high": np.random.uniform(105.0, 110.0, rows),
        "low": np.random.uniform(95.0, 100.0, rows),
        "close": np.random.uniform(100.0, 105.0, rows),
        "volume": np.random.randint(100, 1000, rows)
    })
    return df

async def run_pipeline():
    print("--- Quadrium E2E Integration Pipeline ---")
    
    # 1. Init DBs
    print("[1] Initializing databases...")
    await init_sqlite()
    get_duckdb()
    
    # 2. Fetch/Create Data
    print("[2] Creating sample data...")
    df = create_sample_data(rows=200)
    
    # 3. Train Model
    exp_id = "e2e_test"
    print(f"[3] Training RL agent (experiment: {exp_id})...")
    trainer = Trainer(experiment_id=exp_id, df=df, agent_type="ppo")
    # Quick train
    run_id = trainer.train(total_timesteps=100)
    print(f"    -> Training complete. Run ID: {run_id}")
    
    # 4. Backtest Model
    print("[4] Running backtest...")
    model_path = str(settings.resolve_path("models") / exp_id / "model")
    backtester = BacktestEngine(
        experiment_id=exp_id,
        df=df,
        agent_type="ppo",
        model_path=model_path,
        instrument="TEST_SYMBOL"
    )
    backtest_id = backtester.run()
    print(f"    -> Backtest complete. ID: {backtest_id}")
    print(f"    -> Total Trades: {len(backtester.trades)}")
    
    # 5. Prop Firm Evaluation
    print("[5] Evaluating against Prop Firm constraints...")
    profile = PropFirmProfile(
        name="FTMO 100k",
        account_size=Decimal('100000'),
        max_overall_drawdown_pct=Decimal('0.10'),
        drawdown_type=DrawdownType.STATIC,
        max_daily_loss_pct=Decimal('0.05'),
        daily_loss_includes_floating=True,
        daily_reset_timezone="UTC",
        phases=[ChallengePhase(name="Phase 1", profit_target_pct=Decimal('0.10'), min_trading_days=1)]
    )
    
    equity_arr = np.array(backtester.equity_curve)
    result = PropFirmSimulator.evaluate(
        profile=profile,
        trades=backtester.trades,
        initial_balance=Decimal('100000'),
        equity_curve=equity_arr
    )
    
    print(f"\n--- Prop Firm Challenge Result ---")
    print(f"Status: {result['status']}")
    print(f"Detail: {result['detail']}")
    
    # Cleanup
    close_duckdb()
    await close_sqlite()
    print("\nPipeline finished successfully.")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
