from typing import Any

import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

from app.core.logging import get_logger

log = get_logger(__name__)


class QuadriumTradingEnv(gym.Env):
    """
    Custom Gymnasium environment for Forex/Metals trading.
    This environment tracks a single instrument over a dataset, allowing long, short, or flat positions.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(self, df: pd.DataFrame, initial_balance: float = 10000.0,
                 transaction_fee_percent: float = 0.0001,
                 window_size: int = 20,
                 reward_scaling: float = 1e-4):
        super().__init__()

        self.df = df.reset_index(drop=True)
        self.initial_balance = initial_balance
        self.transaction_fee_percent = transaction_fee_percent
        self.window_size = window_size
        self.reward_scaling = reward_scaling

        # Determine feature columns (exclude time/date columns)
        exclude_cols = {"time", "date", "timestamp"}
        self.feature_cols = [c for c in self.df.columns if c.lower() not in exclude_cols]

        # Expect price columns to compute PnL
        self.close_idx = self.feature_cols.index([c for c in self.feature_cols if c.lower() == "close"][0])

        # Action space: continuous from -1 (max short) to +1 (max long)
        self.action_space = spaces.Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)

        # State space: window of features + current position + current balance
        # Flattened shape: (window_size * num_features) + 2
        obs_shape = (self.window_size * len(self.feature_cols) + 2,)
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=obs_shape, dtype=np.float32)

        self.reset()

    def reset(self, seed: int | None = None, options: dict[str, Any] | None = None) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)

        # Start at the point where we have a full window
        self.current_step = self.window_size - 1

        self.balance = self.initial_balance
        self.net_worth = self.initial_balance
        self.max_net_worth = self.initial_balance

        # Position sizing (number of units held). >0 is long, <0 is short.
        self.position = 0.0
        self.current_price = self._get_close_price(self.current_step)

        return self._get_observation(), self._get_info()

    def _get_close_price(self, step: int) -> float:
        return float(self.df.iloc[step][self.feature_cols[self.close_idx]])

    def _get_observation(self) -> np.ndarray:
        # Get historical window
        window_start = self.current_step - self.window_size + 1
        window_end = self.current_step + 1

        obs_df = self.df.iloc[window_start:window_end][self.feature_cols]
        obs_features = obs_df.values.flatten()

        # Append account state (scaled)
        account_state = np.array([
            self.position,  # Current position
            self.balance / self.initial_balance  # Scaled balance
        ], dtype=np.float32)

        return np.concatenate([obs_features, account_state])

    def step(self, action: np.ndarray) -> tuple[np.ndarray, float, bool, bool, dict]:
        self.current_step += 1

        # Check if episode is done
        done = self.current_step >= len(self.df) - 1
        if done:
            return self._get_observation(), 0.0, True, False, self._get_info()

        # Execute action
        target_position_pct = float(action[0]) # -1.0 to 1.0

        current_price = self._get_close_price(self.current_step)

        # Simple execution model:
        # target_position_pct * net_worth gives the target exposure in dollars
        target_exposure = target_position_pct * self.net_worth
        target_units = target_exposure / current_price

        # Calculate trade size to reach target
        trade_units = target_units - self.position

        # Calculate transaction costs
        trade_value = abs(trade_units) * current_price
        transaction_cost = trade_value * self.transaction_fee_percent

        # Update balance and position
        self.balance -= transaction_cost
        self.position = target_units

        # PnL from price change (since previous step)
        price_diff = current_price - self._get_close_price(self.current_step - 1)
        step_pnl = self.position * price_diff

        # Update net worth
        self.net_worth = self.balance + (self.position * current_price)
        self.max_net_worth = max(self.max_net_worth, self.net_worth)

        # Calculate reward
        # Using step PnL minus costs, scaled down
        reward = (step_pnl - transaction_cost) * self.reward_scaling

        # Risk constraints: if we lose 50% of the account, terminate
        if self.net_worth <= self.initial_balance * 0.5:
            done = True
            reward = -1.0 # Large penalty

        return self._get_observation(), reward, done, False, self._get_info()

    def _get_info(self) -> dict:
        return {
            "step": self.current_step,
            "net_worth": self.net_worth,
            "balance": self.balance,
            "position": self.position,
        }
