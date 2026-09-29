from app.data.time_profile import OffsetPeriod, TimeProfile

TP_UTC = TimeProfile(
    profile_id="test_utc",
    broker="fake",
    server="fake",
    symbol="EURUSD",
    source_time_basis="UTC",
    periods=[OffsetPeriod(effective_from=None, effective_to=None, offset_hours=0.0)]
)
import os
from datetime import UTC, datetime

import pytest
from app.data.providers.mt5 import MT5Error, MT5Provider

from tests.fakes.fake_mt5 import FakeMT5Client


def test_mt5_provider_fake_metadata():
    client = FakeMT5Client()
    provider = MT5Provider(client=client, time_profile=TP_UTC)
    spec = provider.get_instrument_spec("EURUSD")
    
    assert spec.canonical_symbol == "EURUSD"
    assert spec.digits == 5
    assert spec.profit_currency == "USD"
    
def test_mt5_provider_fake_account_rejection():
    client = FakeMT5Client(currency="EUR")
    provider = MT5Provider(client=client, time_profile=TP_UTC)
    with pytest.raises(MT5Error, match="Only USD accounts are supported"):
        provider.connect()
        
def test_mt5_provider_fake_bars():
    client = FakeMT5Client()
    provider = MT5Provider(client=client, time_profile=TP_UTC)
    
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
    provider = MT5Provider(client=client, time_profile=TP_UTC)
    
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
    provider = MT5Provider(client=client, time_profile=TP_UTC)
    provider.connect()
    
    spec = provider.get_instrument_spec("EURUSD")
    assert spec.canonical_symbol == "EURUSD"
    provider.disconnect()

def test_mt5_provider_account_info_failure():
    client = FakeMT5Client()
    provider = MT5Provider(client=client, time_profile=TP_UTC)
    
    # Mock account_info to fail
    client.account_info = lambda: None
    
    with pytest.raises(MT5Error, match="Failed to fetch account info"):
        provider.connect()
        
    assert not provider._connected
    assert not client.initialized

def test_mt5_provider_account_currency_failure():
    client = FakeMT5Client()
    provider = MT5Provider(client=client, time_profile=TP_UTC)
    
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
    provider = MT5Provider(client=client, time_profile=TP_UTC)
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
    client.ticks = [(base_ts + 105 * 60, 1.0, 1.1, 1.0, 100, 0)]
    provider = MT5Provider(client=client, time_profile=TP_UTC)
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
    provider = MT5Provider(client=client, time_profile=TP_UTC)
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
    
    with pytest.raises(ValueError, match="Source defect: Raw chunk for EURUSD M1 contains 2 duplicated rows"):
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
    client.ticks = [(base_ts + 30, 1.0, 1.1, 1.0, 100, 0)]
    provider = MT5Provider(client=client, time_profile=TP_UTC)
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
    client.ticks = [(base_ts + 1439 * 60 + 30, 1.0, 1.1, 1.0, 100, 0)]
    provider = MT5Provider(client=client, time_profile=TP_UTC)
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
    provider = MT5Provider(client=client, time_profile=TP_UTC)
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
    provider = MT5Provider(client=client, time_profile=TP_UTC)
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

def test_mt5_provider_preserves_utc():
    from datetime import UTC, datetime

    from app.data.providers.mt5 import MT5Provider
    
    class MockMT5ClientForTZ(FakeMT5Client):
        def __init__(self):
            super().__init__()
            self.received_start = None
            self.received_end = None
            
        def copy_rates_range(self, symbol, timeframe, date_from, date_to):
            self.received_start = date_from
            self.received_end = date_to
            return super().copy_rates_range(symbol, timeframe, date_from, date_to)
            
    client = MockMT5ClientForTZ()
    client.rates = [(1672617600, 1.0, 1.0, 1.0, 1.0, 100, 10, 100)]
    provider = MT5Provider(client=client, time_profile=TP_UTC)
    provider.connect()
    
    start_utc = datetime(2023, 1, 2, tzinfo=UTC)
    end_utc = datetime(2023, 1, 3, tzinfo=UTC)
    
    provider.fetch_bars("EURUSD", "M1", start_utc, end_utc)
    
    assert client.received_start is not None
    assert client.received_start == int(start_utc.timestamp())



def test_ingestion_sparse_dataset_pass():
    from datetime import UTC, datetime, time
    from pathlib import Path

    from app.data.catalog import DatasetCatalog
    from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
    from app.data.datasets import DatasetManager
    from app.data.downloader import MT5Downloader
    
    temp_dir = Path("test_ingest_sparse")
    temp_dir.mkdir(exist_ok=True)
    manager = DatasetManager(temp_dir)
    catalog = DatasetCatalog(temp_dir / "catalog.duckdb")
    
    client = FakeMT5Client()
    rates = []
    base_ts = 1672617600
    for i in range(1440):
        if i == 10:
            continue
        rates.append((base_ts + i * 60, 1.1000, 1.1010, 1.0990, 1.1005, 100, 10, 100))
    client.rates = rates
    client.ticks = []
    
    provider = MT5Provider(client=client, time_profile=TP_UTC)
    provider.connect()
    
    config = ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=0, start_time=time(0, 0), end_day=4, end_time=time(23, 59))]
    )
    calendar = ConfigurableCalendar(config)
    workflow = MT5Downloader(provider, manager, catalog, calendar)
    start = datetime(2023, 1, 2, tzinfo=UTC)
    end = datetime(2023, 1, 3, tzinfo=UTC)
    
    artifact = workflow.download_bars("EURUSD", "M1", start, end, chunk_days=1)
    
    assert artifact.quality_report.quality_status == "PASS"
    assert artifact.quality_report.coverage_status == "SPARSE"
    assert artifact.quality_report.source_sparse_bars == 1
    assert artifact.quality_report.ticks_present_bar_missing == 0
    assert artifact.quality_report.unexpected_missing_bars == 0
    
    import shutil
    shutil.rmtree(temp_dir)

def test_ingestion_ticks_present_bar_missing_fail():
    from datetime import UTC, datetime, time
    from pathlib import Path

    import pytest
    from app.data.catalog import DatasetCatalog
    from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
    from app.data.datasets import DatasetManager
    from app.data.downloader import MT5Downloader
    
    temp_dir = Path("test_ingest_corrupted")
    temp_dir.mkdir(exist_ok=True)
    manager = DatasetManager(temp_dir)
    catalog = DatasetCatalog(temp_dir / "catalog.duckdb")
    
    client = FakeMT5Client()
    rates = []
    base_ts = 1672617600
    for i in range(1440):
        if i == 10:
            continue
        rates.append((base_ts + i * 60, 1.1000, 1.1010, 1.0990, 1.1005, 100, 10, 100))
    client.rates = rates
    client.ticks = [(base_ts + 10 * 60 + 30, 1.0, 1.1, 1.0, 100, 0)]
    
    provider = MT5Provider(client=client, time_profile=TP_UTC)
    provider.connect()
    
    config = ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=0, start_time=time(0, 0), end_day=4, end_time=time(23, 59))]
    )
    calendar = ConfigurableCalendar(config)
    workflow = MT5Downloader(provider, manager, catalog, calendar)
    start = datetime(2023, 1, 2, tzinfo=UTC)
    end = datetime(2023, 1, 3, tzinfo=UTC)
    
    with pytest.raises(ValueError, match="Dataset ingestion failed quality checks"):
        workflow.download_bars("EURUSD", "M1", start, end, chunk_days=1)
        
    import shutil
    shutil.rmtree(temp_dir)


def test_ingestion_multi_chunk_stitching(tmp_path):
    from datetime import UTC, datetime, timedelta
    from unittest.mock import MagicMock

    from app.data.catalog import DatasetCatalog
    from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
    from app.data.datasets import DatasetManager
    from app.data.downloader import MT5Downloader
    from app.data.providers.mt5 import MT5Provider
    
    manager = DatasetManager(tmp_path)
    catalog = DatasetCatalog(tmp_path / "catalog.duckdb")
    
    client = MagicMock()
    client.initialize.return_value = True
    client.terminal_info.return_value = MagicMock()
    client.account_info.return_value = MagicMock(company="Fake", server="Fake", currency="USD", leverage=100)
    
    sym = MagicMock()
    sym.name = "EURUSD"
    sym.digits = 5
    sym.point = 1e-5
    sym.trade_tick_size = 1e-5
    sym.trade_tick_value = 1.0
    sym.trade_contract_size = 100000.0
    sym.volume_min = 0.01
    sym.volume_max = 500.0
    sym.volume_step = 0.01
    sym.currency_margin = "EUR"
    sym.currency_profit = "USD"
    sym.trade_calc_mode = 0
    client.symbol_info.return_value = sym
    
    def mock_copy_rates_range(symbol, timeframe, start, end):
        from datetime import UTC, datetime

        import pandas as pd
        s_dt = start if not isinstance(start, int) else datetime.fromtimestamp(start, tz=UTC)
        e_dt = end if not isinstance(end, int) else datetime.fromtimestamp(end, tz=UTC)
        dates = pd.date_range(s_dt, e_dt, inclusive='left', freq='1min')
        if len(dates) == 0: return None
        df = pd.DataFrame({'time': dates})
        df['time'] = [int(d.timestamp()) for d in dates]
        df['open'] = 1.0
        df['high'] = 1.0
        df['low'] = 1.0
        df['close'] = 1.0
        df['tick_volume'] = 10
        df['spread'] = 1
        df['real_volume'] = 0
        return df.to_records(index=False)
    client.copy_rates_range.side_effect = mock_copy_rates_range
    client.copy_ticks_range.return_value = None
    
    provider = MT5Provider(time_profile=TP_UTC)
    provider.client = client
    
    config = ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=0, start_time=datetime.min.time(), end_day=4, end_time=datetime.max.time())]
    )
    calendar = ConfigurableCalendar(config)
    downloader = MT5Downloader(provider, manager, catalog, calendar)
    
    start_ts = datetime(2023, 1, 2, 0, 0, tzinfo=UTC)  # Monday
    end_ts = datetime(2023, 1, 4, 0, 0, tzinfo=UTC)    # Wednesday (2 days)
    
    artifact = downloader.download_bars("EURUSD", "M1", start_ts, end_ts, chunk_days=1)
    
    assert artifact.quality_report.coverage_status == "FULL"
    assert artifact.quality_report.quality_status == "PASS"
    df = manager.load_canonical(artifact.dataset_id)
    assert len(df) == 2880  # 2 days * 1440
    assert df['timestamp'].min() == start_ts
    assert df['timestamp'].max() == end_ts - timedelta(minutes=1)

def test_ingestion_dataset_identity_differs_by_range(tmp_path):
    from datetime import UTC, datetime
    from unittest.mock import MagicMock

    from app.data.catalog import DatasetCatalog
    from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
    from app.data.datasets import DatasetManager
    from app.data.downloader import MT5Downloader
    from app.data.providers.mt5 import MT5Provider
    
    manager = DatasetManager(tmp_path)
    catalog = DatasetCatalog(tmp_path / "catalog.duckdb")
    
    client = MagicMock()
    client.initialize.return_value = True
    client.terminal_info.return_value = MagicMock()
    client.account_info.return_value = MagicMock(company="Fake", server="Fake", currency="USD", leverage=100)
    
    sym = MagicMock()
    sym.name = "EURUSD"
    sym.digits = 5
    sym.point = 1e-5
    sym.trade_tick_size = 1e-5
    sym.trade_tick_value = 1.0
    sym.trade_contract_size = 100000.0
    sym.volume_min = 0.01
    sym.volume_max = 500.0
    sym.volume_step = 0.01
    sym.currency_margin = "EUR"
    sym.currency_profit = "USD"
    sym.trade_calc_mode = 0
    client.symbol_info.return_value = sym
    
    def mock_copy_rates_range(symbol, timeframe, start, end):
        from datetime import UTC, datetime

        import pandas as pd
        s_dt = start if not isinstance(start, int) else datetime.fromtimestamp(start, tz=UTC)
        e_dt = end if not isinstance(end, int) else datetime.fromtimestamp(end, tz=UTC)
        dates = pd.date_range(s_dt, e_dt, inclusive='left', freq='1min')
        if len(dates) == 0: return None
        df = pd.DataFrame({'time': dates})
        df['time'] = [int(d.timestamp()) for d in dates]
        df['open'] = 1.0
        df['high'] = 1.0
        df['low'] = 1.0
        df['close'] = 1.0
        df['tick_volume'] = 10
        df['spread'] = 1
        df['real_volume'] = 0
        return df.to_records(index=False)
    client.copy_rates_range.side_effect = mock_copy_rates_range
    client.copy_ticks_range.return_value = None
            
    provider = MT5Provider(time_profile=TP_UTC)
    provider.client = client
    
    config = ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=0, start_time=datetime.min.time(), end_day=4, end_time=datetime.max.time())]
    )
    calendar = ConfigurableCalendar(config)
    downloader = MT5Downloader(provider, manager, catalog, calendar)
    
    start_ts1 = datetime(2023, 1, 2, 0, 0, tzinfo=UTC)
    end_ts1 = datetime(2023, 1, 3, 0, 0, tzinfo=UTC)
    
    start_ts2 = datetime(2023, 1, 3, 0, 0, tzinfo=UTC)
    end_ts2 = datetime(2023, 1, 4, 0, 0, tzinfo=UTC)
    
    art1 = downloader.download_bars("EURUSD", "M1", start_ts1, end_ts1, chunk_days=1)
    art2 = downloader.download_bars("EURUSD", "M1", start_ts2, end_ts2, chunk_days=1)
    
    assert art1.dataset_id != art2.dataset_id
    assert art1.dataset_hash != art2.dataset_hash
    
    datasets = catalog.query_datasets()
    assert len(datasets) == 2


def test_source_bar_outside_session_fails(tmp_path):
    from datetime import UTC, datetime, time
    from unittest.mock import MagicMock

    import pandas as pd
    from app.data.catalog import DatasetCatalog
    from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
    from app.data.datasets import DatasetManager
    from app.data.downloader import MT5Downloader
    from app.data.providers.mt5 import MT5Provider

    manager = DatasetManager(tmp_path)
    catalog = DatasetCatalog(tmp_path / "catalog.duckdb")

    config = ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=0, start_time=time(0, 0), end_day=0, end_time=time(12, 0))]
    )
    calendar = ConfigurableCalendar(config)

    dates = pd.date_range(datetime(2023, 1, 2, 0, 0, tzinfo=UTC), datetime(2023, 1, 2, 13, 0, tzinfo=UTC), inclusive='left', freq='1min')

    client = MagicMock()
    client.initialize.return_value = True
    client.terminal_info.return_value = MagicMock()
    client.account_info.return_value = MagicMock(company="Fake", server="Fake", currency="USD", leverage=100)
    sym = MagicMock()
    sym.name = "EURUSD"
    sym.digits = 5
    sym.point = 1e-5
    sym.trade_tick_size = 1e-5
    sym.trade_tick_value = 1.0
    sym.trade_contract_size = 100000.0
    sym.volume_min = 0.01
    sym.volume_max = 500.0
    sym.volume_step = 0.01
    sym.currency_margin = "EUR"
    sym.currency_profit = "USD"
    sym.trade_calc_mode = 0
    client.symbol_info.return_value = sym
    client.map_timeframe.return_value = 1

    def mock_copy_rates_range(symbol, timeframe, start, end):
        df = pd.DataFrame({'time': [int(d.timestamp()) for d in dates]})
        df['open'] = 1.0
        df['high'] = 1.0
        df['low'] = 1.0
        df['close'] = 1.0
        df['tick_volume'] = 10
        df['spread'] = 1
        df['real_volume'] = 0
        return df.to_records(index=False)

    client.copy_rates_range.side_effect = mock_copy_rates_range
    client.copy_ticks_range.return_value = None

    provider = MT5Provider(time_profile=TP_UTC)
    provider.client = client

    downloader = MT5Downloader(provider, manager, catalog, calendar)

    import pytest
    with pytest.raises(ValueError, match="unexpected_extra_bars"):
        downloader.download_bars("EURUSD", "M1", datetime(2023, 1, 2, 0, 0, tzinfo=UTC), datetime(2023, 1, 2, 23, 59, tzinfo=UTC))

def test_multiple_weekly_windows(tmp_path):
    from datetime import UTC, datetime, time
    from unittest.mock import MagicMock

    import pandas as pd
    from app.data.catalog import DatasetCatalog
    from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
    from app.data.datasets import DatasetManager
    from app.data.downloader import MT5Downloader
    from app.data.providers.mt5 import MT5Provider

    manager = DatasetManager(tmp_path)
    catalog = DatasetCatalog(tmp_path / "catalog.duckdb")

    config = ConfigurableCalendarConfig(
        sessions=[
            SessionWindow(start_day=0, start_time=time(0, 0), end_day=0, end_time=time(10, 0)),
            SessionWindow(start_day=0, start_time=time(14, 0), end_day=0, end_time=time(20, 0))
        ]
    )
    calendar = ConfigurableCalendar(config)

    dates1 = pd.date_range(datetime(2023, 1, 2, 0, 0, tzinfo=UTC), datetime(2023, 1, 2, 10, 0, tzinfo=UTC), inclusive='left', freq='1min')
    dates2 = pd.date_range(datetime(2023, 1, 2, 14, 0, tzinfo=UTC), datetime(2023, 1, 2, 20, 0, tzinfo=UTC), inclusive='left', freq='1min')
    dates = dates1.union(dates2)

    client = MagicMock()
    client.initialize.return_value = True
    client.terminal_info.return_value = MagicMock()
    client.account_info.return_value = MagicMock(company="Fake", server="Fake", currency="USD", leverage=100)
    sym = MagicMock()
    sym.name = "EURUSD"
    sym.digits = 5
    sym.point = 1e-5
    sym.trade_tick_size = 1e-5
    sym.trade_tick_value = 1.0
    sym.trade_contract_size = 100000.0
    sym.volume_min = 0.01
    sym.volume_max = 500.0
    sym.volume_step = 0.01
    sym.currency_margin = "EUR"
    sym.currency_profit = "USD"
    sym.trade_calc_mode = 0
    client.symbol_info.return_value = sym
    client.map_timeframe.return_value = 1

    def mock_copy_rates_range(symbol, timeframe, start, end):
        # Only return what's in dates that falls into [start, end)
        df = pd.DataFrame({'time': [int(d.timestamp()) for d in dates]})
        s_val = start if isinstance(start, int) else int(start.timestamp())
        e_val = end if isinstance(end, int) else int(end.timestamp())
        mask = (df['time'] >= s_val) & (df['time'] < e_val)
        dff = df[mask].copy()
        if dff.empty: return None
        dff['open'] = 1.0
        dff['high'] = 1.0
        dff['low'] = 1.0
        dff['close'] = 1.0
        dff['tick_volume'] = 10
        dff['spread'] = 1
        dff['real_volume'] = 0
        return dff.to_records(index=False)

    client.copy_rates_range.side_effect = mock_copy_rates_range
    client.copy_ticks_range.return_value = None

    provider = MT5Provider(time_profile=TP_UTC)
    provider.client = client
    downloader = MT5Downloader(provider, manager, catalog, calendar)

    artifact = downloader.download_bars("EURUSD", "M1", datetime(2023, 1, 2, 0, 0, tzinfo=UTC), datetime(2023, 1, 2, 23, 59, tzinfo=UTC))

    assert artifact.quality_report.quality_status == "PASS"
    assert artifact.quality_report.unexpected_extra_bars == 0
    assert artifact.quality_report.unexpected_missing_bars == 0
    assert artifact.quality_report.coverage_status == "FULL"
