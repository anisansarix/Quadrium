import typing

import gymnasium as gym
import numpy as np
import pandas as pd
from app.risk.policy_risk import DeterministicRiskEngine
from app.simulator.domain import ActionProposal, MarketObservation
from app.simulator.policy_sim import PolicySimulator
from gymnasium.spaces import Box


class QuadriumEnv(gym.Env):
    def __init__(self, df: pd.DataFrame, simulator: PolicySimulator, risk_engine: DeterministicRiskEngine):
        super().__init__()
        self.df = df
        self.simulator = simulator
        self.risk_engine = risk_engine
        
        # Action space: continuous [-1.0, 1.0] representing target weight
        self.action_space = Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)
        
        # Determine observation space based on first valid row
        self.feature_cols = [c for c in df.columns if c not in ['timestamp', 'open', 'high', 'low', 'close', 'tick_volume', 'real_volume', 'spread', 'data_state', 'feature_state']]
        self.observation_space = Box(
            low=-np.inf, high=np.inf, shape=(len(self.feature_cols),), dtype=np.float32
        )
        
        self.current_idx = 0
        self.current_obs: MarketObservation | None = None
        
    def _get_obs_vector(self, obs: MarketObservation) -> np.ndarray:
        vec = np.array([obs.features.get(c, 0.0) for c in self.feature_cols], dtype=np.float32)
        # Ensure finite
        if not np.all(np.isfinite(vec)):
            vec = np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0)
        return vec

    def _advance_warmup(self):
        while self.current_idx < len(self.df):
            row = self.df.iloc[self.current_idx]
            from app.domain.models import FeatureState
            
            # WARMUP or INVALID skip to the first valid obs for reset
            if row['feature_state'] == FeatureState.WARMUP or pd.isna(row['open']):
                # Advance simulator internally without actions
                self.simulator.process_step(None, row, next_obs_time=row['timestamp']) 
                self.current_idx += 1
            else:
                break

    def reset(self, *, seed: int | None = None, options: dict | None = None) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        
        self.simulator.reset()
        
        self.current_idx = 0
        self._advance_warmup()
        
        if self.current_idx >= len(self.df):
            raise ValueError("Dataset contains no valid observable rows after warmup.")
            
        row = self.df.iloc[self.current_idx]
        
        # Initial observation
        self.current_obs = MarketObservation(
            timestamp=row['timestamp'],
            symbol=self.simulator.symbol,
            features={c: float(row[c]) for c in self.feature_cols if not pd.isna(row[c])},
            close_price=float(row['close']) if not pd.isna(row['close']) else 0.0
        )
        
        return self._get_obs_vector(self.current_obs), {}

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
        if isinstance(self.action_space, Box) and not self.action_space.contains(action):
                action = np.clip(action, self.action_space.low, self.action_space.high)
            
        weight = float(action[0])
        if not np.isfinite(weight):
            weight = 0.0
            
        proposal = ActionProposal(symbol=self.simulator.symbol, target_weight=weight)
        
        # 1. Risk Engine
        risk_decision = self.risk_engine.evaluate(proposal)
        approved_action = risk_decision.approved_action
        
        # 2. Simulator
        if self.current_idx >= len(self.df):
            self.simulator.process_step(None, None)
            shape = tuple(self.observation_space.shape) if self.observation_space.shape else (len(self.feature_cols),)
            return np.zeros(shape, dtype=np.float32), 0.0, True, False, {"reason": "END_OF_DATA"}
            
        row = self.df.iloc[self.current_idx]
        
        # Calculate next_obs_time based on next row's timestamp if available
        next_obs_time = self.df.iloc[self.current_idx + 1]['timestamp'] if self.current_idx + 1 < len(self.df) else row['timestamp']
        
        prev_equity = self.simulator.get_portfolio_state(
            self.simulator.last_valid_close or 0.0, 
            self.simulator.last_valid_spread or 0.0, 
            self.simulator.current_time or row['timestamp']
        ).equity
        
        step_res = self.simulator.process_step(approved_action, row, next_obs_time=next_obs_time)
        
        self.current_idx += 1
        
        # 3. Reward (incremental marked-to-market return)
        curr_equity = step_res.portfolio.equity
        reward = (curr_equity - prev_equity) / prev_equity if prev_equity > 0 else 0.0
        
        # 4. Observation
        shape = tuple(self.observation_space.shape) if self.observation_space.shape else (len(self.feature_cols),)
        obs_vec = self._get_obs_vector(step_res.observation) if step_res.observation else np.zeros(shape, dtype=np.float32)
        
        info = step_res.info.copy()
        info['risk_decision'] = risk_decision.reason_code
        info['realized_pnl'] = step_res.realized_pnl
        
        terminated = step_res.is_done
        truncated = False
        
        return obs_vec, float(reward), terminated, truncated, info






