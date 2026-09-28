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
    
@pytest.mark.skipif(os.environ.get("QUADRIUM_MT5_INTEGRATION") != "1", reason="Opt-in MT5 real test")
def test_real_mt5_connection():
    from app.data.providers.mt5_client import RealMT5Client
    client = RealMT5Client()
    provider = MT5Provider(client=client)
    provider.connect()
    
    spec = provider.get_instrument_spec("EURUSD")
    assert spec.canonical_symbol == "EURUSD"
    provider.disconnect()

def test_mt5_provider_account_info_failure():
    client = FakeMT5Client()
    provider = MT5Provider(client=client)
    
    # Mock account_info to fail
    client.account_info = lambda: None
    
    with pytest.raises(MT5Error, match="Failed to fetch account info"):
        provider.connect()
        
    assert not provider._connected
    assert not client.initialized

def test_mt5_provider_account_currency_failure():
    client = FakeMT5Client()
    provider = MT5Provider(client=client)
    
    client.account_currency = "EUR"
    
    with pytest.raises(MT5Error, match="Unsupported account currency: EUR"):
        provider.connect()
        
    assert not provider._connected
    assert not client.initialized

def test_end_to_end_ingestion():
    from pathlib import Path

    from app.data.catalog import DatasetCatalog
    from app.data.datasets import DatasetManager
    from app.data.downloader import MT5Downloader
    
    # Use in-memory duckdb or temp
    temp_dir = Path("test_ingest_temp")
    temp_dir.mkdir(exist_ok=True)
    manager = DatasetManager(temp_dir)
    catalog = DatasetCatalog(temp_dir / "catalog.duckdb")
    
    client = FakeMT5Client()
    # fake bars over 2 days (Jan 1 is Sunday, Jan 2 is Monday)
    client.rates = [
        (1672531200, 1.1000, 1.1010, 1.0990, 1.1005, 100, 10, 100),
        (1672617600, 1.1005, 1.1020, 1.1000, 1.1015, 150, 12, 150),
        (1672703940, 1.1005, 1.1020, 1.1000, 1.1015, 150, 12, 150), # Jan 2 23:59
        (1672704000, 1.1005, 1.1020, 1.1000, 1.1015, 150, 12, 150) # Jan 3 00:00
    ]
    provider = MT5Provider(client=client)
    provider.connect()
    
    workflow = MT5Downloader(provider, manager, catalog)
    start = datetime(2023, 1, 1, tzinfo=UTC)
    end = datetime(2023, 1, 3, tzinfo=UTC)
    
    artifact = workflow.download_bars("EURUSD", "M1", start, end, chunk_days=1)
    
    assert artifact.dataset_id
    assert artifact.dataset_hash
    
    # Reload dataset by hash
    res = catalog.lookup_by_hash(artifact.dataset_hash)
    assert len(res) == 1
    
    # File existence
    assert Path(artifact.canonical_path).exists()
    
    # Validate dataframe
    df = manager.load_canonical(artifact.dataset_id)
    assert len(df) == 4
    assert df["symbol"].iloc[0] == "EURUSD"
    assert df["timeframe"].iloc[0] == "M1"
    assert df["timestamp"].dt.tz is not None # UTC
    
    import shutil
    shutil.rmtree(temp_dir)
