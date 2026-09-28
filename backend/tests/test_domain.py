from app.domain.models import InstrumentSpec


def test_instrument_spec_creation():
    spec = InstrumentSpec(
        broker_symbol="EURUSD",
        canonical_symbol="EURUSD",
        asset_class="FX",
        digits=5,
        point=0.00001,
        tick_size=0.00001,
        tick_value=1.0,
        contract_size=100000.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        margin_currency="USD",
        profit_currency="USD",
        execution_mode="MARKET",
        trading_sessions={},
        stop_level=0
    )
    assert spec.contract_size == 100000.0

def test_xauusd_contract_size():
    spec = InstrumentSpec(
        broker_symbol="XAUUSD",
        canonical_symbol="XAUUSD",
        asset_class="METALS",
        digits=2,
        point=0.01,
        tick_size=0.01,
        tick_value=1.0,
        contract_size=100.0, # Not 100,000!
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        margin_currency="USD",
        profit_currency="USD",
        execution_mode="MARKET",
        trading_sessions={},
        stop_level=0
    )
    assert spec.contract_size == 100.0
