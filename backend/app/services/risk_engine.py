from dataclasses import dataclass
from datetime import datetime

import numpy as np


@dataclass
class Trade:
    id: str
    instrument: str
    direction: str # 'long' or 'short'
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    lot_size: float
    pnl: float # net profit including commissions/swap
    commission: float = 0.0
    swap: float = 0.0

@dataclass
class DrawdownResult:
    max_drawdown_abs: float
    max_drawdown_pct: float

@dataclass
class TrailingDrawdownResult:
    max_drawdown_abs: float
    max_drawdown_pct: float

@dataclass
class DailyPnL:
    date: str
    pnl: float

@dataclass
class DailyLoss:
    date: str
    max_loss_abs: float
    max_loss_pct: float

@dataclass
class ConsistencyResult:
    passed: bool
    max_day_share: float
    max_trade_share: float

class RiskEngine:
    """
    Deterministic, stateless risk calculation engine.
    All methods are pure functions operating on trade/equity data.
    """

    @staticmethod
    def max_drawdown(equity_curve: np.ndarray) -> DrawdownResult:
        """Peak-to-trough maximum drawdown (absolute and %)."""
        if len(equity_curve) == 0:
            return DrawdownResult(0.0, 0.0)

        peak = equity_curve[0]
        max_dd_abs = 0.0
        max_dd_pct = 0.0

        for val in equity_curve:
            if val > peak:
                peak = val
            dd_abs = peak - val
            dd_pct = dd_abs / peak if peak > 0 else 0.0

            if dd_abs > max_dd_abs:
                max_dd_abs = dd_abs
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        return DrawdownResult(
            max_drawdown_abs=max_dd_abs,
            max_drawdown_pct=max_dd_pct
        )

    @staticmethod
    def drawdown_trailing(equity_curve: np.ndarray, initial_balance: float) -> TrailingDrawdownResult:
        """Trailing drawdown from highest watermark relative to initial balance."""
        if len(equity_curve) == 0:
            return TrailingDrawdownResult(0.0, 0.0)

        peak = initial_balance
        max_dd_abs = 0.0
        max_dd_pct = 0.0

        for val in equity_curve:
            if val > peak:
                peak = val
            dd_abs = peak - val
            # Trailing DD % is usually calculated based on the initial balance (prop firm style)
            dd_pct = dd_abs / initial_balance if initial_balance > 0 else 0.0

            if dd_abs > max_dd_abs:
                max_dd_abs = dd_abs
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        return TrailingDrawdownResult(
            max_drawdown_abs=max_dd_abs,
            max_drawdown_pct=max_dd_pct
        )

    @staticmethod
    def daily_pnl(trades: list[Trade], timezone: str = "UTC") -> list[DailyPnL]:
        """Daily P&L with timezone-aware day boundaries."""
        import pandas as pd
        if not trades:
            return []

        daily = {}
        for t in trades:
            date_str = pd.Timestamp(t.exit_time).tz_convert(timezone).strftime("%Y-%m-%d") if hasattr(pd.Timestamp(t.exit_time), "tz_convert") and pd.Timestamp(t.exit_time).tz else pd.Timestamp(t.exit_time).strftime("%Y-%m-%d")

            if date_str not in daily:
                daily[date_str] = 0.0
            daily[date_str] += t.pnl

        result = [DailyPnL(date=k, pnl=v) for k, v in sorted(daily.items())]
        return result

    @staticmethod
    def daily_loss(trades: list[Trade], start_balance: float, timezone: str = "UTC", include_floating: bool = True) -> list[DailyLoss]:
        """
        Daily loss calculation. In a real engine, this requires minute-by-minute equity curve.
        Since we only have trades here, we estimate based on trade exit times.
        For true daily loss (prop firm), we need floating PnL integrated.
        """
        # Simplistic version: just based on closed trades
        daily_pnls = RiskEngine.daily_pnl(trades, timezone)
        results = []
        current_balance = start_balance

        for d in daily_pnls:
            loss = 0.0
            if d.pnl < 0:
                loss = abs(d.pnl)

            loss_pct = loss / current_balance if current_balance > 0 else 0.0
            results.append(DailyLoss(
                date=d.date,
                max_loss_abs=loss,
                max_loss_pct=loss_pct
            ))
            current_balance += d.pnl

        return results

    @staticmethod
    def profit_factor(trades: list[Trade]) -> float:
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = sum(abs(t.pnl) for t in trades if t.pnl < 0)
        if gross_loss == 0:
            return 999.0 if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @staticmethod
    def sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.0, periods: int = 252) -> float:
        if len(returns) < 2:
            return 0.0
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        if std_return == 0:
            return 0.0
        # Annualized
        return float(((mean_return - risk_free_rate) / std_return) * np.sqrt(periods))

    @staticmethod
    def sortino_ratio(returns: np.ndarray, risk_free_rate: float = 0.0, periods: int = 252) -> float:
        if len(returns) < 2:
            return 0.0
        mean_return = np.mean(returns)
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return 999.0
        downside_std = np.std(downside_returns)
        if downside_std == 0:
            return 999.0
        return float(((mean_return - risk_free_rate) / downside_std) * np.sqrt(periods))

    @staticmethod
    def expectancy(trades: list[Trade]) -> float:
        if not trades:
            return 0.0
        avg_trade = sum(t.pnl for t in trades) / len(trades)
        return avg_trade

    @staticmethod
    def win_rate(trades: list[Trade]) -> float:
        if not trades:
            return 0.0
        wins = sum(1 for t in trades if t.pnl > 0)
        return wins / len(trades)

    @staticmethod
    def max_consecutive_losses(trades: list[Trade]) -> int:
        max_losses = 0
        current_losses = 0
        for t in trades:
            if t.pnl < 0:
                current_losses += 1
                if current_losses > max_losses:
                    max_losses = current_losses
            else:
                current_losses = 0
        return max_losses

    @staticmethod
    def recovery_factor(net_profit: float, max_dd: float) -> float:
        if max_dd == 0:
            return 999.0 if net_profit > 0 else 0.0
        return net_profit / max_dd

    @staticmethod
    def win_loss_ratio(trades: list[Trade]) -> float:
        wins = [t.pnl for t in trades if t.pnl > 0]
        losses = [abs(t.pnl) for t in trades if t.pnl < 0]
        if not wins or not losses:
            return 0.0
        avg_win = sum(wins) / len(wins)
        avg_loss = sum(losses) / len(losses)
        return avg_win / avg_loss

    @staticmethod
    def consistency_score(trades: list[Trade], daily_pnl: list[DailyPnL], threshold_pct: float) -> ConsistencyResult:
        """
        Check if any single day or single trade exceeds threshold_pct of total profit.
        """
        if not daily_pnl:
            return ConsistencyResult(True, 0.0, 0.0)

        profits = [d.pnl for d in daily_pnl if d.pnl > 0]
        if not profits:
            return ConsistencyResult(True, 0.0, 0.0)

        total_profit = sum(profits)
        max_day = max(profits)
        max_day_share = max_day / total_profit
        
        max_trade_share = 0.0
        trade_profits = [t.pnl for t in trades if t.pnl > 0]
        if trade_profits:
            max_trade_share = max(trade_profits) / sum(trade_profits)

        passed = max_day_share <= threshold_pct and max_trade_share <= threshold_pct
        return ConsistencyResult(
            passed=passed,
            max_day_share=max_day_share,
            max_trade_share=max_trade_share
        )
