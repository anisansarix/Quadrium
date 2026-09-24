import asyncio
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # type: ignore[assignment]
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.logging import get_logger
from app.core.database import get_db_session
from app.models.db import LiveTradingSession
from app.ml.agents.finrl_agents import AgentFactory
from app.ml.environments.forex_env import QuadriumTradingEnv
from app.services.fetchers.mt5_fetcher import MT5Fetcher
from app.config import settings

log = get_logger(__name__)

class LiveTradingEngine:
    _active_tasks: dict[str, asyncio.Task] = {}
    
    @classmethod
    async def start_session(cls, session_id: str, experiment_id: str, symbol: str, timeframe: str, config: dict):
        if session_id in cls._active_tasks:
            raise ValueError("Session is already running")
            
        task = asyncio.create_task(cls._run_loop(session_id, experiment_id, symbol, timeframe, config))
        cls._active_tasks[session_id] = task
        log.info(f"Started live trading session {session_id} for {symbol}")
        
    @classmethod
    async def stop_session(cls, session_id: str):
        if session_id in cls._active_tasks:
            cls._active_tasks[session_id].cancel()
            del cls._active_tasks[session_id]
            log.info(f"Stopped live trading session {session_id}")
            
            async with get_db_session() as db:
                stmt = select(LiveTradingSession).where(LiveTradingSession.id == session_id)
                res = await db.execute(stmt)
                session = res.scalar_one_or_none()
                if session:
                    session.status = "stopped"
                    session.stopped_at = datetime.now()
                    await db.commit()
            
    @classmethod
    async def get_active_sessions(cls) -> list[str]:
        return list(cls._active_tasks.keys())
        
    @classmethod
    async def _run_loop(cls, session_id: str, experiment_id: str, symbol: str, timeframe: str, config: dict):
        # Force symbol to uppercase for MT5
        symbol = symbol.upper()
        
        try:
            log.info(f"Session {session_id} booting up model {experiment_id}")
            
            # Load model
            model_path = str(settings.resolve_path("models") / experiment_id / "model")
            
            # Dummy env to load the model correctly
            fetcher = MT5Fetcher()
            end = datetime.now()
            start = end - timedelta(days=1)
            dummy_df = await fetcher.fetch_historical_data(symbol, timeframe, start, end)
            
            dummy_env = QuadriumTradingEnv(df=dummy_df, initial_balance=25000.0)
            model = AgentFactory.load_agent("ppo", model_path, env=dummy_env)
            
            current_position = 0
            
            # Map timeframe string to MT5 timeframe ID for candle checking
            mt5_tf_map = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1}
            tf_id = mt5_tf_map.get(timeframe, mt5.TIMEFRAME_M5)
            
            last_processed_time = None
            latest_prediction = 0.0
            latest_prediction_time = None
            
            while True:
                def _fetch_state():
                    if not mt5.initialize(): return None, None
                    acc = mt5.account_info()
                    rates = mt5.copy_rates_from_pos(symbol, tf_id, 0, 1)
                    return acc, rates
                    
                acc_info, rates = await asyncio.to_thread(_fetch_state)
                
                # Fast loop monitoring - Update DB Equity
                if acc_info:
                    async with get_db_session() as db:
                        stmt = select(LiveTradingSession).where(LiveTradingSession.id == session_id)
                        res = await db.execute(stmt)
                        session = res.scalar_one_or_none()
                        if session:
                            session.current_balance = acc_info.balance
                            session.current_equity = acc_info.equity
                            # Safely inject latest prediction state into config JSON for frontend
                            current_config = session.config or {}
                            current_config["latest_prediction"] = latest_prediction
                            if latest_prediction_time:
                                current_config["latest_prediction_time"] = latest_prediction_time
                            session.config = current_config.copy()
                            await db.commit()
                
                # Check for new candle to run inference
                if rates is not None and len(rates) > 0:
                    current_candle_time = rates[-1]['time']
                    
                    if last_processed_time is None or current_candle_time > last_processed_time:
                        log.info(f"[{session_id}] New candle detected or first run. Fetching latest market state for {symbol}...")
                        last_processed_time = current_candle_time
                        
                        end_dt = datetime.now()
                        start_dt = end_dt - timedelta(days=5)
                        df = await fetcher.fetch_historical_data(symbol, timeframe, start_dt, end_dt)
                        
                        if len(df) < 50:
                            log.warning(f"[{session_id}] Not enough data to form state.")
                        else:
                            env = QuadriumTradingEnv(df=df, initial_balance=acc_info.balance if acc_info else 25000.0)
                            obs, _ = env.reset()
                            
                            done = False
                            while not done:
                                obs, _, done, _, _ = env.step(np.array([0.0]))
                                
                            action, _ = model.predict(obs, deterministic=True)
                            latest_prediction = float(action[0])
                            latest_prediction_time = datetime.now().isoformat()
                            log.info(f"[{session_id}] Model predicted action: {action}")
                            
                            # Lot Sizing
                            if config.get("lot_type") == "auto" and acc_info:
                                risk_pct = float(config.get("risk_pct", 1.0))
                                calculated_lot = max(0.01, round(acc_info.equity * 0.00001 * risk_pct, 2))
                                log.info(f"[{session_id}] Auto Lot Sizing: Eq {acc_info.equity}, Risk {risk_pct}% -> Lot {calculated_lot}")
                            else:
                                calculated_lot = float(config.get("lot_size", 0.1))
                                
                            current_position = await asyncio.to_thread(
                                cls._execute_mt5_trade, symbol, action, current_position, calculated_lot
                            )
                
                # Fast polling loop sleep
                await asyncio.sleep(1.0)
                
        except asyncio.CancelledError:
            log.info(f"Session {session_id} was cancelled.")
        except Exception as e:
            log.error(f"Error in live trading loop {session_id}: {e}")
            async with get_db_session() as db:
                stmt = select(LiveTradingSession).where(LiveTradingSession.id == session_id)
                res = await db.execute(stmt)
                session = res.scalar_one_or_none()
                if session:
                    session.status = "error"
                    session.stopped_at = datetime.now()
                    await db.commit()
                    
    @classmethod
    def _execute_mt5_trade(cls, symbol: str, action: np.ndarray, current_position: float, lot_size: float = 0.1) -> float:
        if not mt5.initialize():
            log.error("MT5 init failed.")
            return current_position

        target_position = 0
        if action[0] > 0.5:
            target_position = 1
        elif action[0] < -0.5:
            target_position = -1
            
        if target_position == current_position:
            return current_position

        log.info(f"Executing trade on MT5: Target Position -> {target_position}, Lot -> {lot_size}")

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
                    mt5.order_send(request)

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
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                return target_position
            else:
                log.error(f"Failed to open position: {res}")
                return 0

        return target_position
