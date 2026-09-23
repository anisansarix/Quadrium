import uuid
import json
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd

from app.ml.environments.forex_env import QuadriumTradingEnv
from app.ml.agents.finrl_agents import AgentFactory
from app.services.risk_engine import Trade, RiskEngine
from app.core.database import get_duckdb
from app.core.logging import get_logger

log = get_logger(__name__)

class BacktestEngine:
    """
    Executes backtests by running a trained model against a dataset
    and recording bar-by-bar equity and discrete trades.
    """
    
    def __init__(
        self,
        experiment_id: str,
        df: pd.DataFrame,
        agent_type: str,
        model_path: str,
        initial_balance: float = 10000.0,
        instrument: str = "UNKNOWN"
    ):
        self.experiment_id = experiment_id
        self.backtest_id = str(uuid.uuid4())
        self.df = df
        self.agent_type = agent_type
        self.model_path = model_path
        self.initial_balance = initial_balance
        self.instrument = instrument
        
        self.env = QuadriumTradingEnv(df=self.df, initial_balance=initial_balance)
        self.model = AgentFactory.load_agent(self.agent_type, self.model_path, env=self.env)
        
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.balance_curve: List[float] = []
        self.timestamps: List[datetime] = []
        
    def run(self) -> str:
        """Run the backtest and save results to DuckDB. Returns backtest_id."""
        log.info("Starting backtest", backtest_id=self.backtest_id, experiment_id=self.experiment_id)
        
        obs, info = self.env.reset()
        
        # Get time column
        time_cols = [c for c in self.df.columns if c.lower() in ["time", "date", "timestamp"]]
        time_col = time_cols[0] if time_cols else None
        
        current_position = 0.0
        current_entry_price = 0.0
        current_entry_time = None
        
        done = False
        while not done:
            step = info["step"]
            dt = self.df.iloc[step][time_col] if time_col else datetime.now()
            
            # Predict
            action, _states = self.model.predict(obs, deterministic=True)
            
            # Step
            obs, reward, done, truncated, info = self.env.step(action)
            
            new_position = info["position"]
            current_price = self.env._get_close_price(step)
            
            # Record Equity
            self.equity_curve.append(info["net_worth"])
            self.balance_curve.append(info["balance"])
            self.timestamps.append(dt)
            
            # Trade inference (simplified):
            # If position changes from 0 to non-zero, open trade
            # If position changes from non-zero to 0, close trade
            # If position flips, close and open
            
            # Tolerate small floats
            def is_zero(v): return abs(v) < 1e-6
            
            if not is_zero(new_position) and is_zero(current_position):
                # Open new trade
                current_entry_price = current_price
                current_entry_time = dt
            
            elif is_zero(new_position) and not is_zero(current_position):
                # Close trade
                direction = "long" if current_position > 0 else "short"
                pnl = (current_price - current_entry_price) * abs(current_position) if direction == "long" else (current_entry_price - current_price) * abs(current_position)
                
                trade = Trade(
                    id=str(uuid.uuid4()),
                    instrument=self.instrument,
                    direction=direction,
                    entry_time=current_entry_time,
                    exit_time=dt,
                    entry_price=Decimal(str(current_entry_price)),
                    exit_price=Decimal(str(current_price)),
                    lot_size=Decimal(str(abs(current_position))),
                    pnl=Decimal(str(pnl))
                )
                self.trades.append(trade)
                
            elif not is_zero(new_position) and not is_zero(current_position):
                # Flips or scale in/out
                # For simplicity in this demo environment, if direction changes, we close and open
                old_dir = "long" if current_position > 0 else "short"
                new_dir = "long" if new_position > 0 else "short"
                
                if old_dir != new_dir:
                    # Close old
                    pnl = (current_price - current_entry_price) * abs(current_position) if old_dir == "long" else (current_entry_price - current_price) * abs(current_position)
                    trade = Trade(
                        id=str(uuid.uuid4()),
                        instrument=self.instrument,
                        direction=old_dir,
                        entry_time=current_entry_time,
                        exit_time=dt,
                        entry_price=Decimal(str(current_entry_price)),
                        exit_price=Decimal(str(current_price)),
                        lot_size=Decimal(str(abs(current_position))),
                        pnl=Decimal(str(pnl))
                    )
                    self.trades.append(trade)
                    # Open new
                    current_entry_price = current_price
                    current_entry_time = dt
            
            current_position = new_position

        # Save to DB
        self._save_results()
        log.info("Backtest completed", backtest_id=self.backtest_id, total_trades=len(self.trades))
        
        return self.backtest_id
        
    def _save_results(self):
        conn = get_duckdb()
        
        # 1. Save trades
        trade_records = []
        for t in self.trades:
            trade_records.append((
                t.id,
                self.backtest_id,
                self.experiment_id,
                t.instrument,
                t.direction,
                t.entry_time,
                t.exit_time,
                float(t.entry_price),
                float(t.exit_price),
                float(t.lot_size),
                float(t.pnl),
                float(t.commission),
                float(t.swap),
                "closed"
            ))
            
        if trade_records:
            conn.executemany("""
                INSERT INTO backtest_trades
                (id, backtest_id, experiment_id, instrument, direction, entry_time, exit_time, 
                 entry_price, exit_price, lot_size, pnl, commission, swap, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, trade_records)
            
        # 2. Save metrics
        eq_arr = np.array(self.equity_curve)
        dd = RiskEngine.max_drawdown(eq_arr)
        
        returns = np.diff(eq_arr) / eq_arr[:-1] if len(eq_arr) > 1 else np.array([])
        sharpe = RiskEngine.sharpe_ratio(returns)
        sortino = RiskEngine.sortino_ratio(returns)
        pf = RiskEngine.profit_factor(self.trades)
        
        conn.execute("""
            INSERT INTO backtest_metrics
            (id, backtest_id, experiment_id, total_trades, win_rate, profit_factor, 
             sharpe_ratio, sortino_ratio, max_drawdown)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            str(uuid.uuid4()),
            self.backtest_id,
            self.experiment_id,
            len(self.trades),
            float(RiskEngine.win_rate(self.trades)),
            float(pf),
            sharpe,
            sortino,
            float(dd.max_drawdown_pct)
        ])
