from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from app.core.decision_pipeline import DecisionPipeline
from app.domain.models import Quote, RiskContext, RiskPolicy, TargetPosition
from app.simulator.engine import SimulatorEngine


class TradingEnv(gym.Env):
    metadata = {"render_modes": ["human"]}  # noqa: RUF012

    def __init__(self, simulator: SimulatorEngine, pipeline: DecisionPipeline, policy: RiskPolicy, data: list[Quote]):
        super().__init__()
        self.simulator = simulator
        self.pipeline = pipeline
        self.policy = policy
        self.data = data
        self.current_step = 0
        self.start_of_day_equity = 10000.0
        self.equity_peak = 10000.0
        
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)
        self.observation_space = spaces.Box(low=0.0, high=np.inf, shape=(2,), dtype=np.float32)

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None):
        super().reset(seed=seed)
        self.current_step = 0
        self.simulator.balance = 10000.0
        self.simulator.equity = 10000.0
        self.simulator.margin = 0.0
        self.simulator.positions = []
        self.start_of_day_equity = 10000.0
        self.equity_peak = 10000.0
        
        if len(self.data) > 0:
            self.simulator.update_quote(self.data[0])
            obs = np.array([self.data[0].bid, self.data[0].ask], dtype=np.float32)
        else:
            obs = np.array([0.0, 0.0], dtype=np.float32)
            
        return obs, {}

    def step(self, action):
        target_weight = float(action[0])
        
        # Build context
        q = self.data[self.current_step]
        spec = self.simulator.instruments.get(q.symbol)
        
        context = RiskContext(
            account=self.simulator.get_account_snapshot(),
            open_positions=self.simulator.positions,
            current_quote=q,
            instrument=spec,
            start_of_day_equity=self.start_of_day_equity,
            equity_peak=self.equity_peak,
            current_time=q.timestamp
        )
        
        target = TargetPosition(symbol=q.symbol, target_weight=target_weight)
        
        # Pipeline execution
        approved_order = self.pipeline.process(target, context, self.policy)
        if approved_order:
            self.simulator.submit_order(approved_order)
            
        self.current_step += 1
        terminated = self.current_step >= len(self.data) - 1
        truncated = False
        
        # Update peak equity
        self.equity_peak = max(self.equity_peak, self.simulator.equity)
        
        reward = 0.0 # Define properly later
        
        info = {
            "equity": self.simulator.equity,
            "balance": self.simulator.balance,
            "drawdown": (self.equity_peak - self.simulator.equity) / self.equity_peak if self.equity_peak > 0 else 0,
        }
        
        if not terminated:
            self.simulator.update_quote(self.data[self.current_step])
            obs = np.array([self.data[self.current_step].bid, self.data[self.current_step].ask], dtype=np.float32)
        else:
            obs = np.zeros(2, dtype=np.float32)
            
        return obs, reward, terminated, truncated, info
