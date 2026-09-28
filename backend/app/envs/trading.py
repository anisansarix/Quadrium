import gymnasium as gym
from gymnasium import spaces
import numpy as np
from app.simulator.engine import SimulatorEngine
from app.domain.models import Quote, OrderIntent, TargetPosition, OrderSide, OrderType, ApprovedOrder, RiskDecision, RiskDecisionState
from typing import Optional, Dict, Any, List

class TradingEnv(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(self, simulator: SimulatorEngine, data: List[Quote]):
        super().__init__()
        self.simulator = simulator
        self.data = data
        self.current_step = 0
        
        # Action space: target net exposure for one symbol (-1.0 to 1.0)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)
        
        # Observation space: very simple for now, just the latest bid/ask
        self.observation_space = spaces.Box(low=0.0, high=np.inf, shape=(2,), dtype=np.float32)

    def reset(self, seed: Optional[int] = None, options: Optional[Dict[str, Any]] = None):
        super().reset(seed=seed)
        self.current_step = 0
        self.simulator.balance = 10000.0
        self.simulator.equity = 10000.0
        self.simulator.positions = []
        
        if len(self.data) > 0:
            self.simulator.update_quote(self.data[0])
            obs = np.array([self.data[0].bid, self.data[0].ask], dtype=np.float32)
        else:
            obs = np.array([0.0, 0.0], dtype=np.float32)
            
        return obs, {}

    def step(self, action):
        target_exposure = action[0]
        # In a real environment, action gets converted to TargetPosition, passed to RiskEngine, then to Simulator
        # For this adapter, we assume the wrapper handles risk and simulator execution
        
        self.current_step += 1
        terminated = self.current_step >= len(self.data) - 1
        truncated = False
        
        if not terminated:
            self.simulator.update_quote(self.data[self.current_step])
            obs = np.array([self.data[self.current_step].bid, self.data[self.current_step].ask], dtype=np.float32)
        else:
            obs = np.zeros(2, dtype=np.float32)
            
        reward = 0.0 # Calculate based on equity change
        return obs, reward, terminated, truncated, {}
