import os
import shutil
from datetime import UTC, datetime, time
from pathlib import Path

import pandas as pd
from app.data.catalog import DatasetCatalog
from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
from app.data.datasets import DatasetManager
from app.data.downloader import MT5Downloader
from app.data.providers.mt5 import MT5Provider
from app.data.time_profile import get_metaquotes_demo_phase1_profile, utc_to_mt5_label


def run_test(start_ts, end_ts, name, calendar):
    print("\n======================================")
    print(f"RUNNING ACCEPTANCE: {name}")
    print("======================================")
    
    temp_dir = Path("data/translation_test")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(exist_ok=True, parents=True)
    manager = DatasetManager(temp_dir)
    catalog = DatasetCatalog(temp_dir / "catalog.duckdb")
    
    kwargs = {}
    server = os.environ.get("QUADRIUM_MT5_SERVER")
    path = os.environ.get("QUADRIUM_MT5_PATH")
    if server: kwargs["server"] = server
    if path: kwargs["path"] = path
    
    time_profile = get_metaquotes_demo_phase1_profile()
    kwargs['time_profile'] = time_profile
    
    provider = MT5Provider(**kwargs)
    try:
        provider.connect()
    except Exception as e:
        print(f"FAIL: MT5Provider connect failed: {e}")
        return False
        
    downloader = MT5Downloader(provider, manager, catalog, calendar)
    
    print("\n--- REQUEST ---")
    print(f"Quadrium UTC Start: {start_ts}")
    print(f"Quadrium UTC End: {end_ts}")
    
    ranges = time_profile.get_subranges(start_ts, end_ts)
    for r_start, r_end, offset in ranges:
        print(f"Translated MT5 Request Start (Raw): {utc_to_mt5_label(r_start, offset)}")
        print(f"Translated MT5 Request End (Raw): {utc_to_mt5_label(r_end, offset)}")
    
    try:
        artifact = downloader.download_bars("EURUSD", "M1", start_ts, end_ts, chunk_days=2)
        print("\n--- RETURN ---")
        df_canonical = pd.read_parquet(artifact.canonical_path)
        print(f"First Canonical UTC: {df_canonical['timestamp'].min()}")
        print(f"Last Canonical UTC: {df_canonical['timestamp'].max()}")
        
        raw_path = manager.raw_dir
        raw_files = list(raw_path.glob("*.parquet"))
        assert len(raw_files) > 0, "Raw Parquet files must exist"
        
        df_raw = pd.concat([pd.read_parquet(f) for f in raw_files])
        
        assert "time" in df_raw.columns, "raw time is present"
        assert "timestamp" not in df_raw.columns, f"raw timestamp is NOT present, but columns are: {df_raw.columns}"
        
        first_raw = df_raw['time'].min()
        last_raw = df_raw['time'].max()  # noqa: F841
        
        assert "timestamp" in df_canonical.columns, "canonical timestamp exists"
        assert df_canonical["timestamp"].dt.tz is not None, "canonical timestamps are UTC (aware)"
        assert str(df_canonical["timestamp"].dt.tz) == "UTC", "canonical timestamps are exactly UTC"
        
        canon_min_epoch = int(df_canonical["timestamp"].min().timestamp())
        assert first_raw != canon_min_epoch, "raw and canonical values represent different time domains"
        
        sm = artifact.manifest.source_metadata
        assert "source_time_basis" in sm, "manifest contains source_time_basis"
        assert "canonical_time_basis" in sm, "manifest contains canonical_time_basis"
        assert "time_profile_id" in sm, "manifest contains time_profile_id"
        
        print("\n--- METRICS ---")
        qr = artifact.quality_report
        print(f"Expected Bars: {qr.expected_bars}")
        print(f"Observed Bars: {qr.observed_bars}")
        print(f"Sparse Bars (NO_TICKS): {qr.source_sparse_bars}")
        print(f"Ticks-Present/Bar-Missing: {qr.ticks_present_bar_missing}")
        print(f"Unexpected Extra Bars: {qr.unexpected_extra_bars}")
        print(f"Quality Status: {qr.quality_status}")
        
        first_valid = df_canonical['timestamp'].min() >= start_ts
        last_valid = df_canonical['timestamp'].max() < end_ts
        print(f"\nFirst Canonical >= Requested Start: {first_valid}")
        print(f"Last Canonical < Requested End: {last_valid}")
        print(f"No Extras: {qr.unexpected_extra_bars == 0}")
        
        if first_valid and last_valid and qr.quality_status == "PASS" and qr.unexpected_extra_bars == 0:
            print("\nRESULT: PASS")
            return True
        else:
            print("\nRESULT: FAIL")
            return False
            
    except Exception as e:
        import traceback
        print(f"\nRESULT: FAIL - Exception during download: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    cal_config = ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=6, start_time=time(21, 0), end_day=4, end_time=time(21, 0))]
    )
    calendar = ConfigurableCalendar(cal_config)
    
    start_ts_1 = datetime(2026, 9, 24, 0, 0, tzinfo=UTC)
    end_ts_1 = datetime(2026, 9, 25, 0, 0, tzinfo=UTC)
    pass_1 = run_test(start_ts_1, end_ts_1, "WEEK 1 (One-Day Window)", calendar)
    
    start_ts_2 = datetime(2026, 9, 21, 0, 0, tzinfo=UTC)
    end_ts_2 = datetime(2026, 9, 28, 0, 0, tzinfo=UTC)
    if pass_1:
        run_test(start_ts_2, end_ts_2, "WEEK 2 (Multi-Day Window)", calendar)
    else:
        print("\nSkipping WEEK 2 because WEEK 1 failed.")
