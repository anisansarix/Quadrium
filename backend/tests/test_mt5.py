import os
from datetime import UTC, datetime

import pytest
from app.data.providers.mt5 import MT5Error, MT5Provider

from tests.fakes.fake_mt5 import FakeMT5Client


def test_mt5_provider_fake_metadata():
    client = FakeMT5Client()
    provider = MT5Provider(client=client)
    spec = provider.get_instrument_spec("EURUSD")
    
    assert spec.canonical_symbol == "EURUSD"
    assert spec.digits == 5
    assert spec.profit_currency == "USD"
    
def test_mt5_provider_fake_account_rejection():
    client = FakeMT5Client(currency="EUR")
    provider = MT5Provider(client=client)
    with pytest.raises(MT5Error, match="Only USD accounts are supported"):
        provider.connect()
        
def test_mt5_provider_fake_bars():
    client = FakeMT5Client()
    provider = MT5Provider(client=client)
    
    # fake bars
    client.rates = [
        (1672531200, 1.1000, 1.1010, 1.0990, 1.1005, 100, 10, 100),
        (1672531260, 1.1005, 1.1020, 1.1000, 1.1015, 150, 12, 150)
    ]
    
    start = datetime(2023, 1, 1, tzinfo=UTC)
    end = datetime(2023, 1, 2, tzinfo=UTC)
    
    df = provider.fetch_bars("EURUSD", "M1", start, end)
    
    assert len(df) == 2
    assert df.iloc[0]["open"] == 1.1000
    assert df.iloc[1]["close"] == 1.1015
    
def test_mt5_provider_fake_ticks():
    client = FakeMT5Client()
    provider = MT5Provider(client=client)
    
    client.ticks = [
        (1672531200, 1.1000, 1.1002, 1.1001, 10, 0),
        (1672531201, 1.1001, 1.1003, 1.1002, 15, 0)
    ]
    
    start = datetime(2023, 1, 1, tzinfo=UTC)
    end = datetime(2023, 1, 2, tzinfo=UTC)
    
    df = provider.fetch_ticks("EURUSD", start, end)
    
    assert len(df) == 2
    assert df.iloc[0]["bid"] == 1.1000
    assert df.iloc[1]["ask"] == 1.1003
    assert df.iloc[0]["spread"] == 0.0002
    
@pytest.mark.skipif(os.environ.get("QUADRIUM_MT5_INTEGRATION") != "1", reason="Opt-in MT5 real test")
def test_real_mt5_connection():
    from app.data.providers.mt5_client import RealMT5Client
    client = RealMT5Client()
    provider = MT5Provider(client=client)
    provider.connect()
    
    spec = provider.get_instrument_spec("EURUSD")
    assert spec.canonical_symbol == "EURUSD"
    provider.disconnect()
