from datetime import UTC, datetime

import pandas as pd
import pytest
from app.data.downloader import RawChunkArtifact
from app.data.time_profile import OffsetPeriod, TimeProfile, get_metaquotes_demo_phase1_profile
from scripts.mt5_time_translation_acceptance import verify_raw_canonical_equivalence


def test_raw_to_canonical_equivalence(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    
    raw_time = 1789959600
    
    df_chunk1 = pd.DataFrame({
        "time": [raw_time, raw_time + 60],
        "symbol": ["EURUSD", "EURUSD"],
        "timeframe": ["M1", "M1"],
        "open": [1.0, 1.1],
        "high": [1.2, 1.3],
        "low": [0.9, 1.0],
        "close": [1.1, 1.2],
        "tick_volume": [10, 20],
        "spread": [1, 2],
        "real_volume": [100, 200]
    })
    
    df_chunk2 = pd.DataFrame({
        "time": [raw_time + 60, raw_time + 120],
        "symbol": ["EURUSD", "EURUSD"],
        "timeframe": ["M1", "M1"],
        "open": [1.1, 1.2],
        "high": [1.3, 1.4],
        "low": [1.0, 1.1],
        "close": [1.2, 1.3],
        "tick_volume": [20, 30],
        "spread": [2, 3],
        "real_volume": [200, 300]
    })
    
    c1_file = str(raw_dir / "c1.parquet")
    c2_file = str(raw_dir / "c2.parquet")
    df_chunk1.to_parquet(c1_file)
    df_chunk2.to_parquet(c2_file)
    
    c1_start = datetime.fromtimestamp(raw_time - 10800, tz=UTC)
    c1_end = datetime.fromtimestamp(raw_time + 60 - 10800, tz=UTC)
    c2_start = datetime.fromtimestamp(raw_time + 60 - 10800, tz=UTC)
    c2_end = datetime.fromtimestamp(raw_time + 120 - 10800, tz=UTC)
    
    rc1 = RawChunkArtifact(path=c1_file, canonical_start=c1_start, canonical_end=c1_end)
    rc2 = RawChunkArtifact(path=c2_file, canonical_start=c2_start, canonical_end=c2_end)
    
    df_canonical = pd.DataFrame({
        "timestamp": [
            datetime.fromtimestamp(raw_time - 10800, tz=UTC),
            datetime.fromtimestamp(raw_time + 60 - 10800, tz=UTC),
            datetime.fromtimestamp(raw_time + 120 - 10800, tz=UTC)
        ],
        "symbol": ["EURUSD", "EURUSD", "EURUSD"],
        "timeframe": ["M1", "M1", "M1"],
        "open": [1.0, 1.1, 1.2],
        "high": [1.2, 1.3, 1.4],
        "low": [0.9, 1.0, 1.1],
        "close": [1.1, 1.2, 1.3],
        "tick_volume": [10, 20, 30],
        "spread": [1, 2, 3],
        "real_volume": [100, 200, 300]
    })
    canonical_file = str(tmp_path / "canonical.parquet")
    df_canonical.to_parquet(canonical_file)
    
    profile = get_metaquotes_demo_phase1_profile()
    start_ts = datetime.fromtimestamp(raw_time - 10800, tz=UTC)
    end_ts = datetime.fromtimestamp(raw_time + 180 - 10800, tz=UTC)
    
    # 1. PASS: Adjacent chunk overlap at exact boundary with identical full payload
    # AND PASS: Correct +3 timestamp translation
    # AND PASS: All required payload fields exactly preserved
    verify_raw_canonical_equivalence([rc1, rc2], canonical_file, profile, start_ts, end_ts)
    
    # 2. FAIL: Duplicate timestamp inside one raw chunk
    df_chunk1_bad = df_chunk1.copy()
    df_chunk1_bad = pd.concat([df_chunk1_bad, df_chunk1_bad.iloc[[-1]]])
    c1_bad_file = str(raw_dir / "c1_bad.parquet")
    df_chunk1_bad.to_parquet(c1_bad_file)
    rc1_bad = RawChunkArtifact(path=c1_bad_file, canonical_start=c1_start, canonical_end=c1_end)
    with pytest.raises(AssertionError, match="Duplicate raw timestamps found WITHIN single chunk"):
        verify_raw_canonical_equivalence([rc1_bad, rc2], canonical_file, profile, start_ts, end_ts)
        
    # 3. FAIL: Duplicate at adjacent boundary with conflicting payload
    df_chunk2_conflict = df_chunk2.copy()
    df_chunk2_conflict.loc[0, "close"] = 999.0
    c2_conflict_file = str(raw_dir / "c2_conflict.parquet")
    df_chunk2_conflict.to_parquet(c2_conflict_file)
    rc2_conflict = RawChunkArtifact(path=c2_conflict_file, canonical_start=c2_start, canonical_end=c2_end)
    with pytest.raises(AssertionError, match="CONFLICTING payload data"):
        verify_raw_canonical_equivalence([rc1, rc2_conflict], canonical_file, profile, start_ts, end_ts)
        
    # 4. FAIL: Wrong +2 translation
    wrong_profile = TimeProfile(
        profile_id="wrong", broker="x", server="y", symbol="z", source_time_basis="UTC",
        periods=[OffsetPeriod(effective_from=None, effective_to=None, offset_hours=2.0)]
    )
    with pytest.raises(AssertionError, match="Row counts differ|raw and canonical values represent different time domains|NOT the shared boundary"):
        verify_raw_canonical_equivalence([rc1, rc2], canonical_file, wrong_profile, start_ts, end_ts)

    # 5. FAIL: Duplicate at adjacent boundary where timestamp is NOT the shared boundary
    df_chunk2_not_shared = pd.DataFrame({
        "time": [raw_time, raw_time + 120],  # Re-including the start time of chunk 1, not boundary
        "symbol": ["EURUSD", "EURUSD"],
        "timeframe": ["M1", "M1"],
        "open": [1.0, 1.2],
        "high": [1.2, 1.4],
        "low": [0.9, 1.1],
        "close": [1.1, 1.3],
        "tick_volume": [10, 30],
        "spread": [1, 3],
        "real_volume": [100, 300]
    })
    c2_not_shared_file = str(raw_dir / "c2_not_shared.parquet")
    df_chunk2_not_shared.to_parquet(c2_not_shared_file)
    rc2_not_shared = RawChunkArtifact(path=c2_not_shared_file, canonical_start=c2_start, canonical_end=c2_end)
    with pytest.raises(AssertionError, match="NOT the shared boundary"):
        verify_raw_canonical_equivalence([rc1, rc2_not_shared], canonical_file, profile, start_ts, end_ts)
        
    # 6. FAIL: Duplicate timestamp in non-adjacent chunks
    df_chunk3 = pd.DataFrame({
        "time": [raw_time, raw_time + 180],  # raw_time duplicated from chunk 1
        "symbol": ["EURUSD", "EURUSD"],
        "timeframe": ["M1", "M1"],
        "open": [1.0, 1.3],
        "high": [1.2, 1.5],
        "low": [0.9, 1.2],
        "close": [1.1, 1.4],
        "tick_volume": [10, 40],
        "spread": [1, 4],
        "real_volume": [100, 400]
    })
    c3_file = str(raw_dir / "c3.parquet")
    df_chunk3.to_parquet(c3_file)
    c3_start = datetime.fromtimestamp(raw_time + 120 - 10800, tz=UTC)
    c3_end = datetime.fromtimestamp(raw_time + 180 - 10800, tz=UTC)
    rc3 = RawChunkArtifact(path=c3_file, canonical_start=c3_start, canonical_end=c3_end)
    with pytest.raises(AssertionError, match="non-adjacent chunks"):
        verify_raw_canonical_equivalence([rc1, rc2, rc3], canonical_file, profile, start_ts, end_ts)
        
    # 7. FAIL: Required canonical field missing from raw
    df_chunk1_missing = df_chunk1.drop(columns=["spread"])
    df_chunk2_missing = df_chunk2.drop(columns=["spread"])
    c1_missing_file = str(raw_dir / "c1_missing.parquet")
    c2_missing_file = str(raw_dir / "c2_missing.parquet")
    df_chunk1_missing.to_parquet(c1_missing_file)
    df_chunk2_missing.to_parquet(c2_missing_file)
    rc1_missing = RawChunkArtifact(path=c1_missing_file, canonical_start=c1_start, canonical_end=c1_end)
    rc2_missing = RawChunkArtifact(path=c2_missing_file, canonical_start=c2_start, canonical_end=c2_end)
    with pytest.raises(AssertionError, match="Required field 'spread' missing from raw"):
        verify_raw_canonical_equivalence([rc1_missing, rc2_missing], canonical_file, profile, start_ts, end_ts)
        
    # 8. FAIL: Required canonical field missing from canonical
    df_canonical_missing = df_canonical.drop(columns=["real_volume"])
    canon_missing_file = str(tmp_path / "canonical_missing.parquet")
    df_canonical_missing.to_parquet(canon_missing_file)
    with pytest.raises(AssertionError, match="Required field 'real_volume' missing from canonical"):
        verify_raw_canonical_equivalence([rc1, rc2], canon_missing_file, profile, start_ts, end_ts)

def test_acceptance_exit_behavior():
    from unittest.mock import patch

    from scripts.mt5_time_translation_acceptance import main
    
    with patch("scripts.mt5_time_translation_acceptance.run_test") as mock_run_test:
        mock_run_test.side_effect = [True, True]
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0
        
        mock_run_test.side_effect = [False]
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
        
        mock_run_test.side_effect = [True, False]
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
