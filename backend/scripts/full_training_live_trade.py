import asyncio
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

from app.core.database import init_sqlite, get_duckdb, close_sqlite, close_duckdb
from app.ml.training.trainer import Trainer
from app.ml.agents.finrl_agents import AgentFactory
from app.ml.environments.forex_env import QuadriumTradingEnv
from app.config import settings
from app.services.fetchers.mt5_fetcher import MT5Fetcher

async def fetch_training_data(symbol: str, timeframe: str, days: int = 365) -> pd.DataFrame:
    fetcher = MT5Fetcher()
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days)
    print(f"Fetching {days} days of {timeframe} data for {symbol} in chunks...")
    
    # Fetch in chunks of 30 days to avoid broker limits
    chunks = []
    current_start = start_dt
    while current_start < end_dt:
        current_end = min(current_start + timedelta(days=30), end_dt)
        print(f"Fetching chunk from {current_start.date()} to {current_end.date()}...")
        try:
            df_chunk = await fetcher.fetch_historical_data(symbol, timeframe, current_start, current_end)
            if not df_chunk.empty:
                chunks.append(df_chunk)
        except Exception as e:
            print(f"Failed to fetch chunk: {e}")
        current_start = current_end
        await asyncio.sleep(1) # Gentle polling
        
    if not chunks:
        raise ValueError("No data fetched.")
        
    full_df = pd.concat(chunks).drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)
    print(f"Total fetched: {len(full_df)} rows.")
    return full_df

def execute_mt5_trade(symbol: str, action: np.ndarray, current_position: float, lot_size: float = 0.1):
    """
    Translates RL action to MT5 trade.
    action is typically continuous in [-1, 1] for position sizing.
    In simplified environments, we might just look at the sign.
    """
    if not mt5.initialize():
        print("MT5 init failed.")
        return current_position

    # We assume action is continuous. Let's just do a simple binary logic for demo purposes.
    # If action > 0.5 -> BUY, if action < -0.5 -> SELL, else HOLD (0)
    target_position = 0
    if action[0] > 0.5:
        target_position = 1
    elif action[0] < -0.5:
        target_position = -1
        
    if target_position == current_position:
        return current_position # Nothing to do

    print(f"Executing trade on MT5: Target Position -> {target_position}")

    # Close existing position if any
    if current_position != 0:
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            for pos in positions:
                tick = mt5.symbol_info_tick(symbol)
                type_ = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
                price = tick.bid if pos.type == 0 else tick.ask
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": pos.volume,
                    "type": type_,
                    "position": pos.ticket,
                    "price": price,
                    "deviation": 20,
                    "magic": 234000,
                    "comment": "Quadrium RL Close",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                result = mt5.order_send(request)
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    print(f"Failed to close position: {result.comment}")

    # Open new position
    if target_position != 0:
        tick = mt5.symbol_info_tick(symbol)
        order_type = mt5.ORDER_TYPE_BUY if target_position == 1 else mt5.ORDER_TYPE_SELL
        price = tick.ask if target_position == 1 else tick.bid
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": "Quadrium RL Open",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Failed to open position: {result.retcode} {result.comment}")
            return 0
        else:
            print(f"Successfully opened position {result.deal}")
            return target_position

    return target_position

async def run_live_trading_loop(model, symbol: str, timeframe: str):
    print(f"--- Starting Live Trading on {symbol} ---")
    current_position = 0
    fetcher = MT5Fetcher()
    
    # We poll every 5 seconds for new state in this demo script
    for i in range(10): 
        print(f"\n[Tick {i+1}/10] Fetching latest state...")
        
        # 1. Fetch enough recent data to compute indicators (e.g. 50 periods)
        end = datetime.now()
        start = end - timedelta(days=5) 
        df = await fetcher.fetch_historical_data(symbol, timeframe, start, end)
        
        if len(df) < 50:
            print("Not enough data to form state.")
            await asyncio.sleep(5)
            continue
            
        # 2. Re-instantiate Env just to get the current observation
        # In a real setup, we would step the environment. 
        # But for inference, we can reset it on the latest slice and jump to the end.
        env = QuadriumTradingEnv(df=df, initial_balance=25000.0)
        obs, _ = env.reset()
        
        # Fast forward env to the last step to get the latest state
        done = False
        while not done:
            obs, _, done, _, info = env.step(np.array([0.0]))
            
        # 3. Predict action for the current state (obs is the terminal observation)
        # Wait, if done=True, the episode is over and env.step returns the last observation.
        # But we want to predict the action for this last observation!
        action, _ = model.predict(obs, deterministic=True)
        print(f"Model predicted action: {action}")
        
        # 4. Execute on MT5
        current_position = execute_mt5_trade(symbol, action, current_position, lot_size=0.1)
        
        print("Waiting 5 seconds for next evaluation...")
        await asyncio.sleep(5)
        
    print("Live trading session ended.")

async def main():
    await init_sqlite()
    get_duckdb()
    
    symbol = "XAUUSD"
    timeframe = "M5"
    exp_id = "xauusd_full_scale_rl_1yr"
    
    # 1. Full-scale training data
    df = await fetch_training_data(symbol, timeframe, days=365)
    
    # 2. Train Model
    print(f"\n--- Starting Full-Scale Training (50,000 timesteps) ---")
    trainer = Trainer(experiment_id=exp_id, df=df, agent_type="ppo")
    run_id = trainer.train(total_timesteps=50000)
    print(f"Training complete. Run ID: {run_id}")
    
    # 3. Load trained model for live trading
    model_path = str(settings.resolve_path("models") / exp_id / "model")
    dummy_env = QuadriumTradingEnv(df=df.head(100), initial_balance=25000.0)
    model = AgentFactory.load_agent("ppo", model_path, env=dummy_env)
    
    # 4. Live Trading Loop
    await run_live_trading_loop(model, symbol, timeframe)
    
    close_duckdb()
    await close_sqlite()

if __name__ == "__main__":
    asyncio.run(main())
