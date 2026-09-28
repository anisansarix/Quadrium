import time
from datetime import UTC, datetime, timedelta

from app.data.catalog import DatasetCatalog
from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
from app.data.datasets import DatasetManager
from app.data.downloader import MT5Downloader
from app.data.providers.mt5 import MT5Provider
from app.data.time_profile import OffsetPeriod, TimeProfile

from tests.fakes.fake_mt5 import FakeMT5Client


def test_end_to_end_translation_preserves_raw_and_canonical(monkeypatch, tmp_path):
    # Set a wild local timezone to prove immunity
    monkeypatch.setenv("TZ", "Pacific/Fiji")
    if hasattr(time, "tzset"):
        time.tzset()
        
    tp = TimeProfile(
        profile_id="test_utc3",
        broker="test",
        server="test",
        symbol="EURUSD",
        source_time_basis="test",
        periods=[OffsetPeriod(effective_from=None, effective_to=None, offset_hours=3.0)]
    )
    
    manager = DatasetManager(tmp_path)
    catalog = DatasetCatalog(tmp_path / "catalog.duckdb")
    
    # 1. Canonical UTC Request
    # 2026-09-24 00:00:00 UTC
    start_utc = datetime(2026, 9, 24, 0, 0, tzinfo=UTC)
    end_utc = datetime(2026, 9, 24, 1, 0, tzinfo=UTC) # 1 hour
    
    client = FakeMT5Client()
    
    # Fake client needs rates.
    # At +3 offset, the raw integer for start_utc should be:
    # 1790208000 + (3 * 3600) = 1790218800
    expected_raw_start = 1790218800
    
    rates = []
    for i in range(60):
        # We populate the fake client with the expected raw timestamps!
        rates.append((expected_raw_start + i * 60, 1.0, 1.1, 0.9, 1.0, 100, 10, 100))
    client.rates = rates
    
    # To assert the request integer shift, we can inspect what the client receives.
    # We patch client.copy_rates_range to spy on the args.
    received_req_start = []
    received_req_end = []
    original_copy = client.copy_rates_range
    
    def spy_copy_rates_range(symbol, timeframe, req_start, req_end):
        received_req_start.append(req_start)
        received_req_end.append(req_end)
        return original_copy(symbol, timeframe, req_start, req_end)
        
    client.copy_rates_range = spy_copy_rates_range
    
    provider = MT5Provider(client=client, time_profile=tp)
    
    # Use a permissive calendar
    from datetime import time as dt_time
    cal = ConfigurableCalendar(ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=0, start_time=dt_time(0, 0), end_day=6, end_time=dt_time(23, 59))]
    ))
    
    downloader = MT5Downloader(provider, manager, catalog, cal)
    artifact = downloader.download_bars("EURUSD", "M1", start_utc, end_utc)
    
    # 2. Translated integer MT5 request
    assert len(received_req_start) == 1
    # Exactly +3h shifted from true UTC
    assert received_req_start[0] == expected_raw_start
    assert received_req_end[0] == expected_raw_start + 3600
    
    # 3. Raw epoch persisted unchanged
    import pandas as pd
    print("Files:", list(tmp_path.rglob("*")))
    raw_files = list((tmp_path / "raw").glob("*.parquet"))
    assert len(raw_files) == 1
    raw_df = pd.read_parquet(raw_files[0])
    assert "time" in raw_df.columns
    assert "timestamp" not in raw_df.columns
    assert raw_df["time"].iloc[0] == expected_raw_start
    
    # 4. Canonical UTC recreated correctly
    canon_df = pd.read_parquet(artifact.canonical_path)
    assert "timestamp" in canon_df.columns
    assert canon_df["timestamp"].iloc[0] == start_utc
    assert canon_df["timestamp"].iloc[-1] == start_utc + timedelta(minutes=59)
    
    # 5. Metadata provenance
    assert artifact.manifest.source_metadata["source_time_basis"] == "test"
    assert artifact.manifest.source_metadata["canonical_time_basis"] == "UTC"
    assert artifact.manifest.source_metadata["time_profile_id"] == "test_utc3"
