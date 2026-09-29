
import numpy as np
import pandas as pd


def calculate_metrics(equity_curve: list[float], realized_pnls: list[float], gross_pnls: list[float], costs: list[float], holding_periods: int, total_steps: int) -> dict[str, float]:
    if not equity_curve:
        return {}
        
    initial_equity = equity_curve[0]
    final_equity = equity_curve[-1]
    total_return = (final_equity - initial_equity) / initial_equity if initial_equity > 0 else 0.0
    
    cumulative_pnl = final_equity - initial_equity
    
    returns = pd.Series(equity_curve).pct_change().dropna()
    volatility = returns.std() * np.sqrt(252 * 24 * 60) # Assuming 1-minute steps roughly
    sharpe_ratio = (returns.mean() / returns.std() * np.sqrt(252 * 24 * 60)) if returns.std() > 0 else 0.0
    
    roll_max = pd.Series(equity_curve).cummax()
    drawdown = (pd.Series(equity_curve) - roll_max) / roll_max
    max_drawdown = drawdown.min()
    
    trade_count = len([p for p in realized_pnls if p != 0.0]) # Simplified
    
    gross_pnl = sum(gross_pnls)
    total_costs = sum(costs)
    realized_pnl = sum(realized_pnls)
    
    time_in_market = holding_periods / total_steps if total_steps > 0 else 0.0
    
    return {
        "total_return": float(total_return),
        "cumulative_pnl": float(cumulative_pnl),
        "volatility": float(volatility),
        "sharpe_ratio": float(sharpe_ratio),
        "max_drawdown": float(max_drawdown),
        "trade_count": float(trade_count),
        "gross_pnl": float(gross_pnl),
        "transaction_costs": float(total_costs),
        "realized_pnl": float(realized_pnl),
        "final_equity": float(final_equity),
        "time_in_market": float(time_in_market)
    }
