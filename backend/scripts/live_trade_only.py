import asyncio
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

from app.core.database import init_sqlite, get_duckdb, close_sqlite, close_duckdb
from app.ml.agents.finrl_agents import AgentFactory
from app.ml.environments.forex_env import QuadriumTradingEnv
from app.config import settings
from app.services.fetchers.mt5_fetcher import MT5Fetcher

def execute_mt5_trade(symbol: str, action: np.ndarray, current_position: float, lot_size: float = 0.1):
    if not mt5.initialize():
        print("MT5 init failed.")
        return current_position

    target_position = 0
    if action[0] > 0.5:
        target_position = 1
    elif action[0] < -0.5:
        target_position = -1
        
    if target_position == current_position:
        return current_position

    print(f"Executing trade on MT5: Target Position -> {target_position}")

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
    
    for i in range(10): 
        print(f"\n[Tick {i+1}/10] Fetching latest state...")
        
        end = datetime.now()
        start = end - timedelta(days=5) 
        df = await fetcher.fetch_historical_data(symbol, timeframe, start, end)
        
        if len(df) < 50:
            print("Not enough data to form state.")
            await asyncio.sleep(5)
            continue
            
        env = QuadriumTradingEnv(df=df, initial_balance=25000.0)
        obs, _ = env.reset()
        
        done = False
        while not done:
            obs, _, done, _, _ = env.step(np.array([0.0]))
            
        action, _ = model.predict(obs, deterministic=True)
        print(f"Model predicted action: {action}")
        
        current_position = execute_mt5_trade(symbol, action, current_position, lot_size=0.1)
        
        print("Waiting 5 seconds for next evaluation...")
        await asyncio.sleep(5)
        
    print("Live trading session ended.")

async def main():
    print("[main] Starting...")
    await init_sqlite()
    print("[main] Databases initialized")
    
    symbol = "XAUUSD"
    timeframe = "M5"
    exp_id = "xauusd_full_scale_rl_1yr"
    
    # Fast dummy env just to load the model shape properly
    print("[main] Fetching dummy data...")
    fetcher = MT5Fetcher()
    end = datetime.now()
    start = end - timedelta(days=1)
    df = await fetcher.fetch_historical_data(symbol, timeframe, start, end)
    print(f"[main] Fetched {len(df)} rows")
    
    print("[main] Loading model...")
    model_path = str(settings.resolve_path("models") / exp_id / "model")
    dummy_env = QuadriumTradingEnv(df=df, initial_balance=25000.0)
    model = AgentFactory.load_agent("ppo", model_path, env=dummy_env)
    print("[main] Model loaded")
    
    await run_live_trading_loop(model, symbol, timeframe)
    
    await close_sqlite()

if __name__ == "__main__":
    asyncio.run(main())
