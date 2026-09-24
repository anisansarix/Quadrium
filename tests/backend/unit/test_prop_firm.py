import pytest

from datetime import datetime
import numpy as np

from app.services.prop_firm import PropFirmSimulator, PropFirmProfile, ChallengePhase, ConsistencyRule
from app.models.enums import DrawdownType, ConsistencyType, ChallengeResult
from app.services.risk_engine import Trade

def test_prop_firm_evaluate_passed():
    profile = PropFirmProfile(
        name="Test",
        account_size=float('10000'),
        max_overall_drawdown_pct=float('0.10'),
        drawdown_type=DrawdownType.STATIC,
        max_daily_loss_pct=float('0.05'),
        daily_loss_includes_floating=True,
        daily_reset_timezone="UTC",
        phases=[ChallengePhase(name="P1", profit_target_pct=float('0.10'), min_trading_days=2)]
    )
    
    trades = [
        Trade("1", "XAUUSD", "long", datetime(2023, 1, 1), datetime(2023, 1, 1), float('1'), float('2'), float('1'), float('600')),
        Trade("2", "XAUUSD", "long", datetime(2023, 1, 2), datetime(2023, 1, 2), float('1'), float('2'), float('1'), float('500'))
    ]
    # No drawdown
    equity = np.array([10000, 10600, 11100])
    
    res = PropFirmSimulator.evaluate(profile, trades, float('10000'), equity)
    assert res["status"] == ChallengeResult.PASSED.value

def test_prop_firm_evaluate_overall_dd_breach():
    profile = PropFirmProfile(
        name="Test",
        account_size=float('10000'),
        max_overall_drawdown_pct=float('0.10'),
        drawdown_type=DrawdownType.TRAILING,
        max_daily_loss_pct=float('0.05'),
        daily_loss_includes_floating=True,
        daily_reset_timezone="UTC"
    )
    trades = [
        Trade("1", "XAUUSD", "long", datetime(2023, 1, 1), datetime(2023, 1, 1), float('1'), float('2'), float('1'), float('-1500'))
    ]
    # Trailing DD max drop is 1500 -> 15% > 10%
    equity = np.array([10000, 8500])
    
    res = PropFirmSimulator.evaluate(profile, trades, float('10000'), equity)
    assert res["status"] == ChallengeResult.FAILED.value
    assert "Overall Drawdown breach" in res["detail"]

def test_prop_firm_evaluate_daily_loss_breach():
    profile = PropFirmProfile(
        name="Test",
        account_size=float('10000'),
        max_overall_drawdown_pct=float('0.10'),
        drawdown_type=DrawdownType.STATIC,
        max_daily_loss_pct=float('0.05'), # Max $500 loss per day on $10k
        daily_loss_includes_floating=True,
        daily_reset_timezone="UTC"
    )
    # Day 1: Lose 600 -> 6% loss
    trades = [
        Trade("1", "XAUUSD", "long", datetime(2023, 1, 1), datetime(2023, 1, 1), float('1'), float('2'), float('1'), float('-600'))
    ]
    equity = np.array([10000, 9400])
    
    res = PropFirmSimulator.evaluate(profile, trades, float('10000'), equity)
    assert res["status"] == ChallengeResult.FAILED.value
    assert "Daily Loss breach" in res["detail"]

def test_prop_firm_evaluate_consistency_breach():
    profile = PropFirmProfile(
        name="Test",
        account_size=float('10000'),
        max_overall_drawdown_pct=float('0.10'),
        drawdown_type=DrawdownType.STATIC,
        max_daily_loss_pct=float('0.05'),
        daily_loss_includes_floating=True,
        daily_reset_timezone="UTC",
        consistency_rules=[ConsistencyRule(ConsistencyType.MAX_DAY_SHARE, float('0.30'))] # Max 30% per day
    )
    trades = [
        # Total profit = 1000. Day 1 = 800 (80%), Day 2 = 200 (20%)
        Trade("1", "XAUUSD", "long", datetime(2023, 1, 1), datetime(2023, 1, 1), float('1'), float('2'), float('1'), float('800')),
        Trade("2", "XAUUSD", "long", datetime(2023, 1, 2), datetime(2023, 1, 2), float('1'), float('2'), float('1'), float('200'))
    ]
    equity = np.array([10000, 10800, 11000])
    
    res = PropFirmSimulator.evaluate(profile, trades, float('10000'), equity)
    assert res["status"] == ChallengeResult.FAILED.value
    assert "Consistency breach" in res["detail"]

def test_prop_firm_evaluate_min_days():
    profile = PropFirmProfile(
        name="Test",
        account_size=float('10000'),
        max_overall_drawdown_pct=float('0.10'),
        drawdown_type=DrawdownType.STATIC,
        max_daily_loss_pct=float('0.05'),
        daily_loss_includes_floating=True,
        daily_reset_timezone="UTC",
        phases=[ChallengePhase(name="P1", profit_target_pct=float('0.10'), min_trading_days=5)]
    )
    trades = [
        Trade("1", "XAUUSD", "long", datetime(2023, 1, 1), datetime(2023, 1, 1), float('1'), float('2'), float('1'), float('1500'))
    ]
    equity = np.array([10000, 11500])
    
    res = PropFirmSimulator.evaluate(profile, trades, float('10000'), equity)
    assert res["status"] == ChallengeResult.IN_PROGRESS.value
    assert "Minimum trading days" in res["detail"]

def test_prop_firm_empty_trades():
    profile = PropFirmProfile("Test", float('10000'), float('0.1'), DrawdownType.STATIC, float('0.05'), True, "UTC")
    res = PropFirmSimulator.evaluate(profile, [], float('10000'), np.array([]))
    assert res["status"] == ChallengeResult.IN_PROGRESS.value
