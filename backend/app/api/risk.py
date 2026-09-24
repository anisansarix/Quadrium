from typing import Any

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.database import get_duckdb
from app.core.logging import get_logger
from app.services.risk_engine import RiskEngine, Trade

log = get_logger(__name__)

router = APIRouter(prefix="/risk")

class CalculateRiskRequest(BaseModel):
    # For ad-hoc risk calculation. In reality, we'd accept trade JSON.
    equity_curve: list[float]
    initial_balance: float = 10000.0
    # trades: list[dict] = [] # Too complex for basic schema, omitting for now

from app.models.schemas import APIResponse

@router.post("/calculate", response_model=APIResponse)
async def calculate_risk(request: CalculateRiskRequest) -> Any:
    """Calculate risk metrics for an ad-hoc equity curve."""
    try:
        curve = np.array(request.equity_curve)

        dd = RiskEngine.max_drawdown(curve)
        trailing_dd = RiskEngine.drawdown_trailing(curve, request.initial_balance)

        return APIResponse(data={
            "max_drawdown_abs": dd.max_drawdown_abs,
            "max_drawdown_pct": dd.max_drawdown_pct,
            "trailing_drawdown_abs": trailing_dd.max_drawdown_abs,
            "trailing_drawdown_pct": trailing_dd.max_drawdown_pct,
        })
    except Exception as e:
        log.error("Failed to calculate risk", error=str(e))
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{experiment_id}", response_model=APIResponse)
async def get_experiment_risk(experiment_id: str) -> Any:
    """Get full risk metrics for an experiment's backtests."""
    try:
        conn = get_duckdb()

        # Fetch trades for this experiment
        trades_df = conn.execute(
            "SELECT * FROM backtest_trades WHERE experiment_id = ? AND status = 'closed'",
            [experiment_id],
        ).fetchdf()

        # Fetch equity curve for this experiment
        equity_df = conn.execute(
            """SELECT be.timestamp, be.equity, be.balance
               FROM backtest_equity be
               JOIN backtest_metrics bm ON be.backtest_id = bm.backtest_id
               WHERE bm.experiment_id = ?
               ORDER BY be.timestamp""",
            [experiment_id],
        ).fetchdf()

        if trades_df.empty and equity_df.empty:
            return APIResponse(
                data={"message": "No backtest data found for this experiment"},
            )

        # Build Trade objects
        trades: list[Trade] = []
        for _, row in trades_df.iterrows():
            trades.append(Trade(
                id=str(row["id"]),
                instrument=str(row["instrument"]),
                direction=str(row["direction"]),
                entry_time=row["entry_time"],
                exit_time=row["exit_time"],
                entry_price=float(row["entry_price"]),
                exit_price=float(row["exit_price"]),
                lot_size=float(row["lot_size"]),
                pnl=float(row["pnl"]),
                commission=float(row.get("commission", 0)),
                swap=float(row.get("swap", 0)),
            ))

        # Build equity curve
        equity_curve = np.array(equity_df["equity"].tolist()) if not equity_df.empty else np.array([])
        initial_balance = float(equity_df["balance"].iloc[0]) if not equity_df.empty else 10000.0

        # Calculate all risk metrics
        dd = RiskEngine.max_drawdown(equity_curve) if len(equity_curve) > 0 else None
        trailing_dd = RiskEngine.drawdown_trailing(equity_curve, initial_balance) if len(equity_curve) > 0 else None
        daily_pnl = RiskEngine.daily_pnl(trades)
        daily_loss = RiskEngine.daily_loss(trades, initial_balance)

        # Daily returns for Sharpe/Sortino
        daily_returns = np.array([d.pnl / initial_balance for d in daily_pnl]) if daily_pnl else np.array([])

        result = {
            "experiment_id": experiment_id,
            "total_trades": len(trades),
            "win_rate": RiskEngine.win_rate(trades),
            "profit_factor": RiskEngine.profit_factor(trades),
            "expectancy": RiskEngine.expectancy(trades),
            "max_consecutive_losses": RiskEngine.max_consecutive_losses(trades),
            "win_loss_ratio": RiskEngine.win_loss_ratio(trades),
            "net_profit": sum(t.pnl for t in trades),
        }

        if dd:
            result["max_drawdown_abs"] = dd.max_drawdown_abs
            result["max_drawdown_pct"] = dd.max_drawdown_pct

        if trailing_dd:
            result["trailing_drawdown_abs"] = trailing_dd.max_drawdown_abs
            result["trailing_drawdown_pct"] = trailing_dd.max_drawdown_pct

        if len(daily_returns) >= 2:
            result["sharpe_ratio"] = RiskEngine.sharpe_ratio(daily_returns)
            result["sortino_ratio"] = RiskEngine.sortino_ratio(daily_returns)

        if dd and dd.max_drawdown_abs > 0:
            result["recovery_factor"] = RiskEngine.recovery_factor(
                sum(t.pnl for t in trades), dd.max_drawdown_abs
            )

        if daily_loss:
            worst_day = max(daily_loss, key=lambda d: d.max_loss_abs)
            result["max_daily_loss_abs"] = worst_day.max_loss_abs
            result["max_daily_loss_pct"] = worst_day.max_loss_pct

        return APIResponse(data=result)

    except Exception as e:
        log.error("Failed to get experiment risk", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
