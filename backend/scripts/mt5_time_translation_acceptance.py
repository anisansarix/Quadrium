import os
import shutil
import sys
from datetime import UTC, datetime, time
from pathlib import Path

import pandas as pd
from app.data.catalog import DatasetCatalog
from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
from app.data.datasets import DatasetManager
from app.data.downloader import MT5Downloader, RawChunkArtifact
from app.data.providers.mt5 import MT5Provider
from app.data.time_profile import get_metaquotes_demo_phase1_profile, utc_to_mt5_label


def verify_raw_canonical_equivalence(raw_chunks: list[RawChunkArtifact], canonical_path, time_profile, start_ts, end_ts):
    df_canonical = pd.read_parquet(canonical_path)
    
    # 1. Load each chunk individually and verify NO internal duplicates
    dfs = []
    chunk_dfs = []
    for chunk in raw_chunks:
        df_chunk = pd.read_parquet(chunk.path)
        if df_chunk.duplicated(subset=["time"]).any():
            raise AssertionError(f"Duplicate raw timestamps found WITHIN single chunk: {chunk.path}")
        
        # Translate to timestamp to know its canonical time
        df_chunk = time_profile.add_canonical_column(df_chunk, raw_col="time", new_col="translated_timestamp")
        chunk_dfs.append((chunk, df_chunk))
        dfs.append(df_chunk)
        
    df_raw_translated = pd.concat(dfs)
    
    assert "time" in df_raw_translated.columns, "raw time is present"
    assert "timestamp" not in df_raw_translated.columns, "raw timestamp is NOT present"
    assert pd.api.types.is_integer_dtype(df_raw_translated['time']), "raw time remains integer/source-domain data"
    
    assert "timestamp" in df_canonical.columns, "canonical timestamp exists"
    assert "time" not in df_canonical.columns, "canonical Parquet does not contain source time"
    assert "time_msc" not in df_canonical.columns, "canonical Parquet does not contain source time_msc"
    assert df_canonical["timestamp"].dt.tz is not None, "canonical timestamps are UTC (aware)"
    assert str(df_canonical["timestamp"].dt.tz) == "UTC", "canonical timestamps are exactly UTC"
    
    first_raw = df_raw_translated['time'].min()
    canon_min_epoch = int(df_canonical["timestamp"].min().timestamp())
    assert first_raw != canon_min_epoch, "raw and canonical values represent different time domains"
    
    # Sort chunks by their canonical_start
    chunk_dfs.sort(key=lambda x: x[0].canonical_start)
    
    # Validate cross-chunk duplicates
    for i in range(len(chunk_dfs) - 1):
        c1, df1 = chunk_dfs[i]
        c2, df2 = chunk_dfs[i+1]
        
        # Shared boundary should be c1.canonical_end (which == c2.canonical_start)
        shared_boundary = c1.canonical_end
        if shared_boundary != c2.canonical_start:
            # They are not strictly adjacent, or there's a gap/overlap in requests, 
            # but we only validate duplicates. Any duplicate outside exact shared boundary is a FAIL.
            pass

    # Find duplicates across all chunks
    dups = df_raw_translated[df_raw_translated.duplicated(subset=["time"], keep=False)]
    if not dups.empty:
        # Check every duplicate group
        for t, group in dups.groupby("time"):
            if len(group) > 2:
                raise AssertionError(f"Duplicate timestamp {t} appears in more than 2 chunks")
            
            # Must appear in exactly two adjacent chunks
            # Must appear in exactly two adjacent chunks
            # To know which chunk they came from, let's just find them in chunk_dfs
            found_in = []
            for idx, (c, df) in enumerate(chunk_dfs):
                if t in df['time'].values:
                    found_in.append(idx)
                    
            if len(found_in) != 2 or abs(found_in[0] - found_in[1]) != 1:
                raise AssertionError("Duplicate timestamp in non-adjacent chunks")
                
            c1, df1 = chunk_dfs[found_in[0]]
            c2, df2 = chunk_dfs[found_in[1]]
            
            shared_boundary = c1.canonical_end
            if shared_boundary != c2.canonical_start:
                raise AssertionError("Duplicate at adjacent boundary where timestamp is NOT the shared boundary")
                
            # The canonical time of this row must exactly equal the shared boundary
            canon_time = group['translated_timestamp'].iloc[0]
            if canon_time != shared_boundary:
                raise AssertionError("Duplicate at adjacent boundary where timestamp is NOT the shared boundary")
                
            # Check payload identity
            payload1 = df1[df1['time'] == t].drop(columns=['translated_timestamp']).iloc[0]
            payload2 = df2[df2['time'] == t].drop(columns=['translated_timestamp']).iloc[0]
            if not payload1.equals(payload2):
                raise AssertionError("Duplicate raw timestamps found across boundary chunks with CONFLICTING payload data")
                
    # Safely drop EXACTLY identical boundary duplicates
    df_raw_filtered = df_raw_translated.drop_duplicates(subset=["time"])
    
    mask = (df_raw_filtered['translated_timestamp'] >= start_ts) & (df_raw_filtered['translated_timestamp'] < end_ts)
    df_raw_filtered = df_raw_filtered[mask].copy()
    
    df_raw_filtered = df_raw_filtered.sort_values("translated_timestamp").reset_index(drop=True)
    df_canonical_sorted = df_canonical.sort_values("timestamp").reset_index(drop=True)
    
    if len(df_raw_filtered) != len(df_canonical_sorted):
        raise AssertionError(f"Row counts differ: {len(df_raw_filtered)} raw vs {len(df_canonical_sorted)} canonical")
    
    assert (df_raw_filtered['translated_timestamp'] == df_canonical_sorted['timestamp']).all(), "Translated raw timestamps do not exactly match canonical timestamps"
    
    # 4. Strengthen raw->canonical field equivalence
    expected_fields = ["symbol", "timeframe", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
    for col in expected_fields:
        if col not in df_raw_filtered.columns:
            raise AssertionError(f"Required field '{col}' missing from raw representation")
        if col not in df_canonical_sorted.columns:
            raise AssertionError(f"Required field '{col}' missing from canonical representation")
            
        if not (df_raw_filtered[col] == df_canonical_sorted[col]).all():
            raise AssertionError(f"Payload column '{col}' differs between raw and canonical representations")
            
    return df_raw_translated, df_canonical

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
        
        raw_chunks = artifact.raw_chunks
        assert len(raw_chunks) > 0, "Raw chunks must exist"
        
        df_raw, df_canonical = verify_raw_canonical_equivalence(raw_chunks, artifact.canonical_path, time_profile, start_ts, end_ts)
        
        print(f"First Canonical UTC: {df_canonical['timestamp'].min()}")
        print(f"Last Canonical UTC: {df_canonical['timestamp'].max()}")
        print(f"First Raw Timestamp (Epoch): {df_raw['time'].min()}")
        print(f"Last Raw Timestamp (Epoch): {df_raw['time'].max()}")
        
        sm = artifact.manifest.source_metadata
        assert "source_time_basis" in sm, "manifest contains source_time_basis"
        assert "canonical_time_basis" in sm, "manifest contains canonical_time_basis"
        assert "time_profile_id" in sm, "manifest contains time_profile_id"
        
        assert sm["source_time_basis"] == "broker_server_wallclock", "source_time_basis is not correct"
        assert sm["canonical_time_basis"] == "UTC", "canonical_time_basis is not correct"
        assert sm["time_profile_id"] == "metaquotes_demo_eurusd_phase1_v1", "time_profile_id is not correct"
        
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

def main():
    cal_config = ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=6, start_time=time(21, 0), end_day=4, end_time=time(21, 0))]
    )
    calendar = ConfigurableCalendar(cal_config)
    
    start_ts_1 = datetime(2026, 9, 24, 0, 0, tzinfo=UTC)
    end_ts_1 = datetime(2026, 9, 25, 0, 0, tzinfo=UTC)
    pass_1 = run_test(start_ts_1, end_ts_1, "WEEK 1 (One-Day Window)", calendar)
    
    if not pass_1:
        sys.exit(1)
        
    start_ts_2 = datetime(2026, 9, 21, 0, 0, tzinfo=UTC)
    end_ts_2 = datetime(2026, 9, 28, 0, 0, tzinfo=UTC)
    pass_2 = run_test(start_ts_2, end_ts_2, "WEEK 2 (Multi-Day Window)", calendar)
    
    if not pass_2:
        sys.exit(1)
        
    sys.exit(0)

if __name__ == "__main__":
    main()
