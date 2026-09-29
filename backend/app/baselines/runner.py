from typing import Any

import numpy as np
from app.baselines.metrics import calculate_metrics
from app.baselines.policies import BaselinePolicy
from app.env.quadrium_env import QuadriumEnv


class BacktestRunner:
    def __init__(self, env: QuadriumEnv, policy: BaselinePolicy):
        self.env = env
        self.policy = policy
        
    def run(self) -> dict[str, Any]:
        _obs_vec, info = self.env.reset()
        done = False
        
        equity_curve = [self.env.simulator.balance]
        realized_pnls: list[float] = []
        gross_pnls: list[float] = []
        costs: list[float] = []
        holding_periods = 0
        total_steps = 0
        
        while not done:
            total_steps += 1
            
            obs = self.env.current_obs
            if not obs:
                break
                
            action_proposal = self.policy.predict(obs)
            
            action_vec = np.array([action_proposal.target_weight], dtype=np.float32)
            
            _obs_vec, _reward, terminated, truncated, info = self.env.step(action_vec)
            
            last_close = self.env.simulator.last_valid_close or 0.0
            last_spread = self.env.simulator.last_valid_spread or 0.0
            cur_time = self.env.simulator.current_time
            if cur_time:
                portfolio = self.env.simulator.get_portfolio_state(last_close, last_spread, cur_time)
                equity_curve.append(portfolio.equity)
                
            realized_pnls.append(info.get('realized_pnl', 0.0))
            
            if self.env.simulator.position:
                holding_periods += 1
                
            done = terminated or truncated
            
        metrics = calculate_metrics(equity_curve, realized_pnls, gross_pnls, costs, holding_periods, total_steps)
        return {
            "metrics": metrics,
            "equity_curve": equity_curve
        }
