from typing import Any

from app.evaluation.ledger import ClosedTrade, EquityRecord


class MetricsCalculator:
    def calculate(self, closed_trades: list[ClosedTrade], equity_curve: list[EquityRecord], initial_balance: float) -> dict[str, Any]:
        if not equity_curve:
            return {
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "trade_count": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "average_net_trade": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "profit_factor": 0.0,
                "turnover": 0.0,
                "total_commission": 0.0,
                "total_swap": 0.0
            }
            
        final_equity = equity_curve[-1].equity
        total_return = (final_equity - initial_balance) / initial_balance if initial_balance > 0 else 0.0
        max_dd = max([t.drawdown for t in equity_curve]) if equity_curve else 0.0
        
        wins = [t for t in closed_trades if t.net_pnl > 0]
        losses = [t for t in closed_trades if t.net_pnl <= 0]
        
        trade_count = len(closed_trades)
        win_rate = len(wins) / trade_count if trade_count > 0 else 0.0
        
        avg_trade = sum([t.net_pnl for t in closed_trades]) / trade_count if trade_count > 0 else 0.0
        
        gross_profit = sum([t.gross_pnl for t in wins])
        gross_loss = abs(sum([t.gross_pnl for t in losses]))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        turnover = sum([t.exit_volume for t in closed_trades])
        total_commission = sum([t.entry_commission + t.exit_commission for t in closed_trades])
        total_swap = sum([t.swap for t in closed_trades])
        
        return {
            "total_return_pct": total_return,
            "max_drawdown_pct": max_dd,
            "trade_count": trade_count,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": win_rate,
            "average_net_trade": avg_trade,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "turnover": turnover,
            "total_commission": total_commission,
            "total_swap": total_swap
        }
