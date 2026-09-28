from unittest.mock import MagicMock

from app.data.mt5_validation import MarginModel, validate_calculations


def test_margin_validation_precision_pass():
    client = MagicMock()
    # Mocking order_calc_profit to return something so it passes
    client.order_calc_profit.return_value = 0.0 # profit logic will calc 0 for 0 diff
    
    # Let's mock order_calc_margin specifically for scenarios
    # Scenarios:
    # 0: BUY 1.0 @ 1.1000  => MT5 returns 3333.33
    # 1: SELL 1.0 @ 1.1000 => MT5 returns 3333.33
    # 2: BUY 0.5 @ 1.1000  => MT5 returns 1666.67
    # 3: SELL 0.5 @ 1.1000 => MT5 returns 1666.67
    # 4: BUY 2.0 @ 1.1000  => MT5 returns 6666.67
    
    def mock_calc_margin(action, symbol, volume, price_open):
        if volume == 1.0: return 3333.33
        if volume == 0.5: return 1666.67
        if volume == 2.0: return 6666.67
        return 0.0
        
    client.order_calc_margin.side_effect = mock_calc_margin
    
    # We also mock profit so that profit validation passes cleanly
    def mock_calc_profit(action, symbol, volume, price_open, price_close):
        # We know quadrium calculates:
        if action == 0:
            return (price_close - price_open) * volume * 100000.0
        else:
            return (price_open - price_close) * volume * 100000.0
            
    client.order_calc_profit.side_effect = mock_calc_profit
    
    spec = MagicMock()
    spec.contract_size = 100000.0
    margin_model = MarginModel(
        leverage=33.0,
        account_currency="USD",
        margin_calculation_mode="0",
        margin_rate=1.0,
        account_currency_decimals=2
    )
    
    report = validate_calculations(client, "EURUSD", spec, margin_model)
    
    assert report.all_passed is True
    
    assert report.margin_diffs[0].passed is True
    assert report.margin_diffs[0].mt5_margin == 3333.33
    assert report.margin_diffs[0].theoretical_margin_normalized == 3333.33
    
    assert report.margin_diffs[2].passed is True
    assert report.margin_diffs[2].mt5_margin == 1666.67
    assert report.margin_diffs[2].theoretical_margin_normalized == 1666.67
    
    assert report.margin_diffs[4].passed is True
    assert report.margin_diffs[4].mt5_margin == 6666.67
    assert report.margin_diffs[4].theoretical_margin_normalized == 6666.67

def test_margin_validation_fail_difference():
    client = MagicMock()
    # Mocking profit to pass
    def mock_calc_profit(action, symbol, volume, price_open, price_close):
        if action == 0: return (price_close - price_open) * volume * 100000.0
        return (price_open - price_close) * volume * 100000.0
    client.order_calc_profit.side_effect = mock_calc_profit
    
    # Mock margin with 1 cent diff
    def mock_calc_margin(action, symbol, volume, price_open):
        return 3333.34 # +1 cent
    client.order_calc_margin.side_effect = mock_calc_margin
    
    spec = MagicMock()
    spec.contract_size = 100000.0
    margin_model = MarginModel(
        leverage=33.0,
        account_currency="USD",
        margin_calculation_mode="0",
        margin_rate=1.0,
        account_currency_decimals=2
    )
    
    report = validate_calculations(client, "EURUSD", spec, margin_model)
    assert report.all_passed is False
    assert report.margin_diffs[0].passed is False

def test_margin_validation_unsupported_mode():
    client = MagicMock()
    client.order_calc_profit.return_value = 0.0
    client.order_calc_margin.return_value = 100.0
    
    spec = MagicMock()
    spec.contract_size = 100000.0
    margin_model = MarginModel(
        leverage=33.0,
        account_currency="USD",
        margin_calculation_mode="CFD",
        margin_rate=1.0,
        account_currency_decimals=2
    )
    
    report = validate_calculations(client, "EURUSD", spec, margin_model)
    assert report.all_passed is False
    assert report.margin_diffs[0].passed is False
    assert report.margin_diffs[0].unsupported is True

def test_margin_validation_invalid_rate():
    client = MagicMock()
    spec = MagicMock()
    spec.contract_size = 100000.0
    margin_model = MarginModel(
        leverage=33.0,
        account_currency="USD",
        margin_calculation_mode="0",
        margin_rate=0.0,
        account_currency_decimals=2
    )
    report = validate_calculations(client, "EURUSD", spec, margin_model)
    assert report.all_passed is False
    assert len(report.margin_diffs) == 0


