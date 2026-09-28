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
    # Generate full Jan 2 (Monday) M1 bars
    rates = []
    base_ts = 1672617600 # 2023-01-02 00:00:00
    for i in range(1440): # 1440 minutes in a day
        rates.append((base_ts + i * 60, 1.1000, 1.1010, 1.0990, 1.1005, 100, 10, 100))
    client.rates = rates
    provider = MT5Provider(client=client)
    provider.connect()
    
    from datetime import time

    from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
    config = ConfigurableCalendarConfig(
        sessions=[
            SessionWindow(start_day=6, start_time=time(22, 0), end_day=4, end_time=time(22, 0))
        ]
    )
    calendar = ConfigurableCalendar(config)
    workflow = MT5Downloader(provider, manager, catalog, calendar)
    start = datetime(2023, 1, 2, tzinfo=UTC)
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
    assert len(df) == 1440
    assert artifact.quality_report.quality_status == "PASS"
    assert df["symbol"].iloc[0] == "EURUSD"
    assert df["timeframe"].iloc[0] == "M1"
    assert df["timestamp"].dt.tz is not None # UTC
    
    import shutil
    shutil.rmtree(temp_dir)

def test_ingestion_fails_internal_gap():
    from pathlib import Path

    from app.data.catalog import DatasetCatalog
    from app.data.datasets import DatasetManager
    from app.data.downloader import MT5Downloader
    
    temp_dir = Path("test_ingest_gap")
    temp_dir.mkdir(exist_ok=True)
    manager = DatasetManager(temp_dir)
    catalog = DatasetCatalog(temp_dir / "catalog.duckdb")
    
    client = FakeMT5Client()
    rates = []
    base_ts = 1672617600
    for i in range(1440):
        if 100 <= i < 110:
            continue # Drop 10 bars
        rates.append((base_ts + i * 60, 1.1000, 1.1010, 1.0990, 1.1005, 100, 10, 100))
    client.rates = rates
    provider = MT5Provider(client=client)
    provider.connect()
    
    from datetime import time

    from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
    config = ConfigurableCalendarConfig(
        sessions=[
            SessionWindow(start_day=6, start_time=time(22, 0), end_day=4, end_time=time(22, 0))
        ]
    )
    calendar = ConfigurableCalendar(config)
    workflow = MT5Downloader(provider, manager, catalog, calendar)
    start = datetime(2023, 1, 2, tzinfo=UTC)
    end = datetime(2023, 1, 3, tzinfo=UTC)
    
    with pytest.raises(ValueError, match="Dataset ingestion failed quality checks"):
        workflow.download_bars("EURUSD", "M1", start, end, chunk_days=1)
        
    import shutil
    shutil.rmtree(temp_dir)

def test_ingestion_fails_duplicate():
    from pathlib import Path

    from app.data.catalog import DatasetCatalog
    from app.data.datasets import DatasetManager
    from app.data.downloader import MT5Downloader
    
    temp_dir = Path("test_ingest_dup")
    temp_dir.mkdir(exist_ok=True)
    manager = DatasetManager(temp_dir)
    catalog = DatasetCatalog(temp_dir / "catalog.duckdb")
    
    client = FakeMT5Client()
    rates = []
    base_ts = 1672617600
    for i in range(1440):
        rates.append((base_ts + i * 60, 1.1000, 1.1010, 1.0990, 1.1005, 100, 10, 100))
        if i == 500:
            rates.append((base_ts + i * 60, 1.1000, 1.1010, 1.0990, 1.1005, 100, 10, 100))
    client.rates = rates
    provider = MT5Provider(client=client)
    provider.connect()
    
    from datetime import time

    from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
    config = ConfigurableCalendarConfig(
        sessions=[
            SessionWindow(start_day=6, start_time=time(22, 0), end_day=4, end_time=time(22, 0))
        ]
    )
    calendar = ConfigurableCalendar(config)
    workflow = MT5Downloader(provider, manager, catalog, calendar)
    start = datetime(2023, 1, 2, tzinfo=UTC)
    end = datetime(2023, 1, 3, tzinfo=UTC)
    
    with pytest.raises(ValueError, match="Duplicate timestamps found"):
        workflow.download_bars("EURUSD", "M1", start, end, chunk_days=1)
        
    import shutil
    shutil.rmtree(temp_dir)

def test_ingestion_fails_missing_first_bar():
    from datetime import time
    from pathlib import Path

    from app.data.catalog import DatasetCatalog
    from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
    from app.data.datasets import DatasetManager
    from app.data.downloader import MT5Downloader
    
    temp_dir = Path("test_ingest_first")
    temp_dir.mkdir(exist_ok=True)
    manager = DatasetManager(temp_dir)
    catalog = DatasetCatalog(temp_dir / "catalog.duckdb")
    
    client = FakeMT5Client()
    rates = []
    base_ts = 1672617600
    for i in range(1, 1440): # Skip 0
        rates.append((base_ts + i * 60, 1.1000, 1.1010, 1.0990, 1.1005, 100, 10, 100))
    client.rates = rates
    provider = MT5Provider(client=client)
    provider.connect()
    
    config = ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=6, start_time=time(22, 0), end_day=4, end_time=time(22, 0))]
    )
    calendar = ConfigurableCalendar(config)
    workflow = MT5Downloader(provider, manager, catalog, calendar)
    start = datetime(2023, 1, 2, tzinfo=UTC)
    end = datetime(2023, 1, 3, tzinfo=UTC)
    
    with pytest.raises(ValueError, match="Dataset ingestion failed quality checks"):
        workflow.download_bars("EURUSD", "M1", start, end, chunk_days=1)
        
    import shutil
    shutil.rmtree(temp_dir)

def test_ingestion_fails_missing_last_bar():
    from datetime import time
    from pathlib import Path

    from app.data.catalog import DatasetCatalog
    from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
    from app.data.datasets import DatasetManager
    from app.data.downloader import MT5Downloader
    
    temp_dir = Path("test_ingest_last")
    temp_dir.mkdir(exist_ok=True)
    manager = DatasetManager(temp_dir)
    catalog = DatasetCatalog(temp_dir / "catalog.duckdb")
    
    client = FakeMT5Client()
    rates = []
    base_ts = 1672617600
    for i in range(1439): # Skip 1439 (last)
        rates.append((base_ts + i * 60, 1.1000, 1.1010, 1.0990, 1.1005, 100, 10, 100))
    client.rates = rates
    provider = MT5Provider(client=client)
    provider.connect()
    
    config = ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=6, start_time=time(22, 0), end_day=4, end_time=time(22, 0))]
    )
    calendar = ConfigurableCalendar(config)
    workflow = MT5Downloader(provider, manager, catalog, calendar)
    start = datetime(2023, 1, 2, tzinfo=UTC)
    end = datetime(2023, 1, 3, tzinfo=UTC)
    
    with pytest.raises(ValueError, match="Dataset ingestion failed quality checks"):
        workflow.download_bars("EURUSD", "M1", start, end, chunk_days=1)
        
    import shutil
    shutil.rmtree(temp_dir)

def test_ingestion_valid_weekend_closure():
    from datetime import time
    from pathlib import Path

    from app.data.catalog import DatasetCatalog
    from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
    from app.data.datasets import DatasetManager
    from app.data.downloader import MT5Downloader
    
    temp_dir = Path("test_ingest_weekend")
    temp_dir.mkdir(exist_ok=True)
    manager = DatasetManager(temp_dir)
    catalog = DatasetCatalog(temp_dir / "catalog.duckdb")
    
    client = FakeMT5Client()
    rates = []
    
    # Friday 2023-01-06 00:00 to 22:00
    base_fri = 1672963200
    for i in range(22 * 60):
        rates.append((base_fri + i * 60, 1.1000, 1.1010, 1.0990, 1.1005, 100, 10, 100))
        
    # Sunday 2023-01-08 22:00 to 24:00
    base_sun = 1673215200
    for i in range(2 * 60):
        rates.append((base_sun + i * 60, 1.1000, 1.1010, 1.0990, 1.1005, 100, 10, 100))
        
    client.rates = rates
    provider = MT5Provider(client=client)
    provider.connect()
    
    config = ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=6, start_time=time(22, 0), end_day=4, end_time=time(22, 0))]
    )
    calendar = ConfigurableCalendar(config)
    workflow = MT5Downloader(provider, manager, catalog, calendar)
    start = datetime(2023, 1, 6, tzinfo=UTC)
    end = datetime(2023, 1, 9, tzinfo=UTC)
    
    artifact = workflow.download_bars("EURUSD", "M1", start, end, chunk_days=1)
    
    assert artifact.quality_report.quality_status == "PASS"
    assert artifact.quality_report.coverage_status == "FULL"
    assert artifact.quality_report.unexpected_missing_bars == 0
        
    import shutil
    shutil.rmtree(temp_dir)

def test_ingestion_half_open_semantics():
    from datetime import time
    from pathlib import Path

    from app.data.catalog import DatasetCatalog
    from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
    from app.data.datasets import DatasetManager
    from app.data.downloader import MT5Downloader
    
    temp_dir = Path("test_ingest_halfopen")
    temp_dir.mkdir(exist_ok=True)
    manager = DatasetManager(temp_dir)
    catalog = DatasetCatalog(temp_dir / "catalog.duckdb")
    
    client = FakeMT5Client()
    rates = []
    base_ts = 1672617600 # 2023-01-02 00:00:00 (Monday)
    # Generate 1440 bars for Jan 2, PLUS 1440 bars for Jan 3
    for i in range(2880): 
        rates.append((base_ts + i * 60, 1.1000, 1.1010, 1.0990, 1.1005, 100, 10, 100))
    client.rates = rates
    provider = MT5Provider(client=client)
    provider.connect()
    
    config = ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=0, start_time=time(0, 0), end_day=4, end_time=time(23, 59))]
    )
    calendar = ConfigurableCalendar(config)
    
    # Request exactly Jan 2 (1 day) in 2 chunks of 12 hours
    workflow = MT5Downloader(provider, manager, catalog, calendar)
    start = datetime(2023, 1, 2, tzinfo=UTC)
    
    # Using 0.5 days doesn't work out of the box if chunk_days is int, wait chunk_days is int.
    # Actually chunk_days=1 is fine if we just request 2 days with chunk_days=1.
    end_2days = datetime(2023, 1, 4, tzinfo=UTC)
    
    artifact = workflow.download_bars("EURUSD", "M1", start, end_2days, chunk_days=1)
    
    # Assert duplicates == 0
    assert artifact.quality_report.duplicate_bars == 0
    assert artifact.quality_report.quality_status == "PASS"
    
    # Assert canonical data min/max
    df_canonical = manager.load_canonical(artifact.dataset_id)
    assert df_canonical['timestamp'].min() == start
    # Max should be strictly less than end_2days
    assert df_canonical['timestamp'].max() < end_2days
    # The last bar should be exactly 1 minute before end_2days
    from datetime import timedelta
    assert df_canonical['timestamp'].max() == end_2days - timedelta(minutes=1)
    
    # Check length: 2 days of M1 = 2880 bars
    assert len(df_canonical) == 2880
    
    import shutil
    shutil.rmtree(temp_dir)
