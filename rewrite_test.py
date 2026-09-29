script = '''import pytest
import pandas as pd
from datetime import datetime, UTC
from pathlib import Path
from app.data.time_profile import get_metaquotes_demo_phase1_profile, TimeProfile, OffsetPeriod
from scripts.mt5_time_translation_acceptance import verify_raw_canonical_equivalence

def test_raw_to_canonical_equivalence(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    
    raw_time = 1789959600
    
    # 1. PASS: Two adjacent chunks contain the same boundary bar with identical values
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
    
    # Chunk 2 overlaps the boundary bar (raw_time + 60) EXACTLY
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
    
    c1_file = raw_dir / "c1.parquet"
    c2_file = raw_dir / "c2.parquet"
    df_chunk1.to_parquet(c1_file)
    df_chunk2.to_parquet(c2_file)
    
    # Canonical removes duplicates naturally (since they are identical)
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
    canonical_file = tmp_path / "canonical.parquet"
    df_canonical.to_parquet(canonical_file)
    
    profile = get_metaquotes_demo_phase1_profile()
    start_ts = datetime.fromtimestamp(raw_time - 10800, tz=UTC)
    end_ts = datetime.fromtimestamp(raw_time + 180 - 10800, tz=UTC)
    
    # PASS: Correct +3 translation produces exact canonical timestamps and all payload matches
    verify_raw_canonical_equivalence([c1_file, c2_file], canonical_file, profile, start_ts, end_ts)
    
    # 2. FAIL: One raw chunk contains the same time twice
    df_chunk1_bad = df_chunk1.copy()
    df_chunk1_bad = pd.concat([df_chunk1_bad, df_chunk1_bad.iloc[[-1]]])
    c1_bad_file = raw_dir / "c1_bad.parquet"
    df_chunk1_bad.to_parquet(c1_bad_file)
    with pytest.raises(AssertionError, match="Duplicate raw timestamps found WITHIN single chunk"):
        verify_raw_canonical_equivalence([c1_bad_file, c2_file], canonical_file, profile, start_ts, end_ts)
        
    # 3. FAIL: Two adjacent chunks contain the same boundary time but conflicting values
    df_chunk2_conflict = df_chunk2.copy()
    df_chunk2_conflict.loc[0, "close"] = 999.0
    c2_conflict_file = raw_dir / "c2_conflict.parquet"
    df_chunk2_conflict.to_parquet(c2_conflict_file)
    with pytest.raises(AssertionError, match="CONFLICTING payload data"):
        verify_raw_canonical_equivalence([c1_file, c2_conflict_file], canonical_file, profile, start_ts, end_ts)
        
    # 4. FAIL: Wrong +2 profile
    wrong_profile = TimeProfile(
        profile_id="wrong", broker="x", server="y", symbol="z", source_time_basis="UTC",
        periods=[OffsetPeriod(effective_from=None, effective_to=None, offset_hours=2.0)]
    )
    with pytest.raises(AssertionError, match="Row counts differ"):
        verify_raw_canonical_equivalence([c1_file, c2_file], canonical_file, wrong_profile, start_ts, end_ts)
        
    # 5. FAIL: Raw timestamp mutation
    df_canonical_mut_time = df_canonical.copy()
    df_canonical_mut_time.loc[0, "timestamp"] = datetime.fromtimestamp(raw_time - 10800 + 1, tz=UTC)
    mut_time_file = tmp_path / "mut_time.parquet"
    df_canonical_mut_time.to_parquet(mut_time_file)
    with pytest.raises(AssertionError, match="Translated raw timestamps do not exactly match"):
        verify_raw_canonical_equivalence([c1_file, c2_file], mut_time_file, profile, start_ts, end_ts)
        
    # 6. FAIL: Payload mutation in spread
    df_canonical_mut_spread = df_canonical.copy()
    df_canonical_mut_spread.loc[0, "spread"] = 999
    mut_spread_file = tmp_path / "mut_spread.parquet"
    df_canonical_mut_spread.to_parquet(mut_spread_file)
    with pytest.raises(AssertionError, match="Payload column 'spread' differs"):
        verify_raw_canonical_equivalence([c1_file, c2_file], mut_spread_file, profile, start_ts, end_ts)
        
    # 7. FAIL: Payload mutation in real_volume
    df_canonical_mut_vol = df_canonical.copy()
    df_canonical_mut_vol.loc[0, "real_volume"] = 999
    mut_vol_file = tmp_path / "mut_vol.parquet"
    df_canonical_mut_vol.to_parquet(mut_vol_file)
    with pytest.raises(AssertionError, match="Payload column 'real_volume' differs"):
        verify_raw_canonical_equivalence([c1_file, c2_file], mut_vol_file, profile, start_ts, end_ts)

def test_acceptance_exit_behavior():
    import sys
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
'''

with open('backend/tests/test_acceptance_raw_to_canonical.py', 'w', encoding='utf-8') as f:
    f.write(script)
