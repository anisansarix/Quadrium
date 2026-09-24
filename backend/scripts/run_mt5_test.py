import asyncio
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from decimal import Decimal

from app.core.database import init_sqlite, get_duckdb, close_sqlite, close_duckdb
from app.ml.training.trainer import Trainer
from app.services.backtest_engine import BacktestEngine
from app.services.prop_firm import PropFirmSimulator, PropFirmProfile, DrawdownType, ChallengePhase
from app.config import settings
from app.services.fetchers.mt5_fetcher import MT5Fetcher

async def run_pipeline():
    print("--- Quadrium MT5 XAUUSD Pipeline ---")
    
    # 1. Init DBs
    print("[1] Initializing databases...")
    await init_sqlite()
    get_duckdb()
    
    # 2. Fetch Data
    print("[2] Fetching XAUUSD data from MT5...")
    fetcher = MT5Fetcher()
    end = datetime.now()
    start = end - timedelta(days=30)
    df = await fetcher.fetch_historical_data("XAUUSD", "H1", start, end)
    print(f"    -> Fetched {len(df)} rows for XAUUSD.")
    
    # 3. Train Model
    exp_id = "mt5_xauusd_test"
    print(f"[3] Training RL agent on XAUUSD (experiment: {exp_id})...")
    trainer = Trainer(experiment_id=exp_id, df=df, agent_type="ppo")
    # Quick train
    run_id = trainer.train(total_timesteps=1000)
    print(f"    -> Training complete. Run ID: {run_id}")
    
    # 4. Backtest Model
    print("[4] Running backtest...")
    model_path = str(settings.resolve_path("models") / exp_id / "model")
    backtester = BacktestEngine(
        experiment_id=exp_id,
        df=df,
        agent_type="ppo",
        model_path=model_path,
        instrument="XAUUSD"
    )
    backtest_id = backtester.run()
    print(f"    -> Backtest complete. ID: {backtest_id}")
    print(f"    -> Total Trades: {len(backtester.trades)}")
    
    # 5. Prop Firm Evaluation
    print("[5] Evaluating against Custom $25k Demo constraints...")
    profile = PropFirmProfile(
        name="Custom Demo 25k",
        account_size=25000.0,
        max_overall_drawdown_pct=0.12, # 12% Max Loss
        drawdown_type=DrawdownType.STATIC,
        max_daily_loss_pct=0.04, # 4% Daily Loss
        daily_loss_includes_floating=True,
        daily_reset_timezone="UTC",
        phases=[ChallengePhase(name="Phase 1", profit_target_pct=0.10, min_trading_days=1)]
    )
    
    equity_arr = np.array(backtester.equity_curve)
    result = PropFirmSimulator.evaluate(
        profile=profile,
        trades=backtester.trades,
        initial_balance=25000.0,
        equity_curve=equity_arr
    )
    
    print(f"\n--- Prop Firm Challenge Result ---")
    print(f"Status: {result['status']}")
    print(f"Detail: {result['detail']}")
    if result.get("metrics"):
        print(f"Profit: {result['metrics'].get('total_profit')}")
        print(f"Max Drawdown: {result['metrics'].get('max_drawdown_pct')}")
    
    # Cleanup
    close_duckdb()
    await close_sqlite()
    print("\nPipeline finished successfully.")

if __name__ == "__main__":
    asyncio.run(run_pipeline())
