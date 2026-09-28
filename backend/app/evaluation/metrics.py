from typing import Dict, Any, List
from app.evaluation.ledger import TradeRecord

class MetricsCalculator:
    def calculate(self, ledger: List[TradeRecord], initial_balance: float) -> Dict[str, Any]:
        if not ledger:
            return {
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "trade_count": 0,
                "win_rate": 0.0,
                "average_trade": 0.0,
                "profit_factor": 0.0,
                "turnover": 0.0
            }
            
        final_balance = ledger[-1].balance
        total_return = (final_balance - initial_balance) / initial_balance
        max_dd = max([t.drawdown for t in ledger])
        
        wins = [t.realized_pnl for t in ledger if t.realized_pnl > 0]
        losses = [t.realized_pnl for t in ledger if t.realized_pnl <= 0]
        
        win_rate = len(wins) / len(ledger) if ledger else 0.0
        avg_trade = sum([t.realized_pnl for t in ledger]) / len(ledger) if ledger else 0.0
        
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        turnover = sum([t.volume for t in ledger])
        
        return {
            "total_return_pct": total_return,
            "max_drawdown_pct": max_dd,
            "trade_count": len(ledger),
            "win_rate": win_rate,
            "average_trade": avg_trade,
            "profit_factor": profit_factor,
            "turnover": turnover
        }
