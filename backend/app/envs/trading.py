from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from app.core.decision_pipeline import DecisionPipeline
from app.domain.models import Quote, RiskContext, RiskPolicy, TargetPosition
from app.simulator.engine import SimulatorEngine
from app.envs.reward import RewardModel, LogEquityChangeReward


class TradingEnv(gym.Env):
    metadata = {"render_modes": ["human"]}  # noqa: RUF012

    def __init__(
        self,
        simulator: SimulatorEngine,
        pipeline: DecisionPipeline,
        policy: RiskPolicy,
        data: list[Quote],
        reward_model: RewardModel | None = None
    ):
        super().__init__()
        self.simulator = simulator
        self.pipeline = pipeline
        self.policy = policy
        self.data = data
        self.reward_model = reward_model or LogEquityChangeReward()
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
        
        # t: context
        q_t = self.data[self.current_step]
        spec = self.simulator.instruments.get(q_t.symbol)
        
        context = RiskContext(
            account=self.simulator.get_account_snapshot(),
            open_positions=self.simulator.positions,
            current_quote=q_t,
            instrument=spec,
            start_of_day_equity=self.start_of_day_equity,
            equity_peak=self.equity_peak,
            current_time=q_t.timestamp
        )
        
        target = TargetPosition(symbol=q_t.symbol, target_weight=target_weight)
        
        prev_account = context.account
        
        # t: pipeline execution and fill
        approved_order = self.pipeline.process(target, context, self.policy)
        if approved_order:
            self.simulator.submit_order(approved_order)
            
        # Update peak equity after action
        self.equity_peak = max(self.equity_peak, self.simulator.equity)
        
        current_account = self.simulator.get_account_snapshot()
        reward = self.reward_model.calculate_reward(prev_account, current_account)
        
        info = {
            "equity": self.simulator.equity,
            "balance": self.simulator.balance,
            "drawdown": (self.equity_peak - self.simulator.equity) / self.equity_peak if self.equity_peak > 0 else 0,
        }
        
        # Advance to t+1
        self.current_step += 1
        terminated = self.current_step >= len(self.data) - 1
        truncated = False
        
        if not terminated:
            q_next = self.data[self.current_step]
            self.simulator.update_quote(q_next)
            obs = np.array([q_next.bid, q_next.ask], dtype=np.float32)
        else:
            obs = np.zeros(2, dtype=np.float32)
            
        return obs, reward, terminated, truncated, info
