import pytest

from datetime import datetime, timezone
import numpy as np

from app.services.risk_engine import RiskEngine, Trade

def test_max_drawdown():
    # equity curve: 1000, 1100, 1050, 1200, 900, 1300
    # Peak at 1200, drops to 900. DD = 300. Pct = 300 / 1200 = 0.25
    curve = np.array([1000, 1100, 1050, 1200, 900, 1300])
    res = RiskEngine.max_drawdown(curve)
    assert float(res.max_drawdown_abs) == 300.0
    assert float(res.max_drawdown_pct) == 0.25

    # No drawdown
    curve2 = np.array([1000, 1100, 1200, 1300])
    res2 = RiskEngine.max_drawdown(curve2)
    assert float(res2.max_drawdown_abs) == 0.0
    assert float(res2.max_drawdown_pct) == 0.0
    
    # Empty
    res3 = RiskEngine.max_drawdown(np.array([]))
    assert float(res3.max_drawdown_abs) == 0.0

def test_drawdown_trailing():
    curve = np.array([1000, 1100, 1050, 1200, 900, 1300])
    # Peak is 1200, drop to 900 = 300. Trailing pct = 300 / 1000 (initial) = 0.30
    res = RiskEngine.drawdown_trailing(curve, float('1000'))
    assert float(res.max_drawdown_abs) == 300.0
    assert float(res.max_drawdown_pct) == 0.30

def test_profit_factor():
    t1 = Trade("1", "XAUUSD", "long", datetime.now(), datetime.now(), float('1'), float('2'), float('1'), float('100'))
    t2 = Trade("2", "XAUUSD", "short", datetime.now(), datetime.now(), float('1'), float('2'), float('1'), float('-50'))
    t3 = Trade("3", "XAUUSD", "long", datetime.now(), datetime.now(), float('1'), float('2'), float('1'), float('200'))
    
    pf = RiskEngine.profit_factor([t1, t2, t3]) # 300 / 50 = 6.0
    assert float(pf) == 6.0
    
    pf2 = RiskEngine.profit_factor([t1, t3]) # Only wins
    assert float(pf2) == 999.0
    
    pf3 = RiskEngine.profit_factor([t2]) # Only losses
    assert float(pf3) == 0.0

def test_daily_pnl():
    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    dt2 = datetime(2023, 1, 2, 12, 0, tzinfo=timezone.utc)
    t1 = Trade("1", "XAUUSD", "long", dt1, dt1, float('1'), float('2'), float('1'), float('100'))
    t2 = Trade("2", "XAUUSD", "short", dt1, dt1, float('1'), float('2'), float('1'), float('-50'))
    t3 = Trade("3", "XAUUSD", "long", dt2, dt2, float('1'), float('2'), float('1'), float('200'))
    
    res = RiskEngine.daily_pnl([t1, t2, t3])
    assert len(res) == 2
    assert res[0].date == "2023-01-01"
    assert float(res[0].pnl) == 50.0
    assert res[1].date == "2023-01-02"
    assert float(res[1].pnl) == 200.0

def test_daily_loss():
    dt1 = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    t1 = Trade("1", "XAU", "long", dt1, dt1, float('1'), float('2'), float('1'), float('-500'))
    res = RiskEngine.daily_loss([t1], float('10000'))
    assert len(res) == 1
    assert float(res[0].max_loss_abs) == 500.0
    assert float(res[0].max_loss_pct) == 0.05

def test_sharpe_sortino():
    returns = np.array([0.01, 0.02, -0.01, 0.03, -0.02])
    sharpe = RiskEngine.sharpe_ratio(returns)
    assert sharpe > 0
    sortino = RiskEngine.sortino_ratio(returns)
    assert sortino > 0

    assert RiskEngine.sharpe_ratio(np.array([0.01])) == 0.0
    assert RiskEngine.sortino_ratio(np.array([0.01])) == 0.0
    assert RiskEngine.sortino_ratio(np.array([0.01, 0.02])) == 999.0

def test_expectancy_winrate():
    t1 = Trade("1", "XAU", "long", datetime.now(), datetime.now(), float('1'), float('2'), float('1'), float('100'))
    t2 = Trade("2", "XAU", "short", datetime.now(), datetime.now(), float('1'), float('2'), float('1'), float('-50'))
    
    assert float(RiskEngine.expectancy([t1, t2])) == 25.0
    assert float(RiskEngine.win_rate([t1, t2])) == 0.5
    
    assert float(RiskEngine.expectancy([])) == 0.0
    assert float(RiskEngine.win_rate([])) == 0.0

def test_max_consecutive_losses():
    t1 = Trade("1", "XAU", "long", datetime.now(), datetime.now(), float('1'), float('2'), float('1'), float('-10'))
    t2 = Trade("2", "XAU", "short", datetime.now(), datetime.now(), float('1'), float('2'), float('1'), float('-10'))
    t3 = Trade("3", "XAU", "long", datetime.now(), datetime.now(), float('1'), float('2'), float('1'), float('10'))
    t4 = Trade("4", "XAU", "short", datetime.now(), datetime.now(), float('1'), float('2'), float('1'), float('-10'))
    
    assert RiskEngine.max_consecutive_losses([t1, t2, t3, t4]) == 2

def test_recovery_factor():
    assert float(RiskEngine.recovery_factor(float('1000'), float('200'))) == 5.0
    assert float(RiskEngine.recovery_factor(float('1000'), float('0'))) == 999.0

def test_win_loss_ratio():
    t1 = Trade("1", "X", "long", datetime.now(), datetime.now(), float('1'), float('2'), float('1'), float('200'))
    t2 = Trade("2", "X", "short", datetime.now(), datetime.now(), float('1'), float('2'), float('1'), float('-100'))
    assert float(RiskEngine.win_loss_ratio([t1, t2])) == 2.0
    assert float(RiskEngine.win_loss_ratio([t1])) == 0.0

def test_consistency_score():
    from app.services.risk_engine import DailyPnL
    d1 = DailyPnL("2023-01-01", float('100'))
    d2 = DailyPnL("2023-01-02", float('50'))
    d3 = DailyPnL("2023-01-03", float('50'))
    
    # Total profit = 200. Max day = 100. Share = 0.5
    res = RiskEngine.consistency_score([], [d1, d2, d3], float('0.6')) # threshold 60%
    assert res.passed
    assert float(res.max_day_share) == 0.5
    
    res2 = RiskEngine.consistency_score([], [d1, d2, d3], float('0.4')) # threshold 40%
    assert not res2.passed
    
    res3 = RiskEngine.consistency_score([], [], float('0.3'))
    assert res3.passed
