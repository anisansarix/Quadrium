from datetime import UTC, datetime

import pandas as pd
import pytest
from app.data.time_profile import OffsetPeriod, TimeProfile, get_metaquotes_demo_phase1_profile
from scripts.mt5_time_translation_acceptance import verify_raw_canonical_equivalence


def test_raw_to_canonical_equivalence(tmp_path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    
    # +3 offset is used in phase1 profile
    # Let's say we have raw time 1000000. 1000000 is 1970-01-12 13:46:40
    # +3 hours = 10800 seconds.
    # So canonical should be 1000000 - 10800 = 989200
    
    raw_time = 1789959600 # Some realistic raw time
    df_raw = pd.DataFrame({
        "time": [raw_time, raw_time + 60],
        "open": [1.0, 1.1],
        "high": [1.2, 1.3],
        "low": [0.9, 1.0],
        "close": [1.1, 1.2],
        "tick_volume": [10, 20]
    })
    
    raw_file = raw_dir / "fake_raw.parquet"
    df_raw.to_parquet(raw_file)
    
    # Correct canonical
    df_canonical = pd.DataFrame({
        "timestamp": [
            datetime.fromtimestamp(raw_time - 10800, tz=UTC),
            datetime.fromtimestamp(raw_time + 60 - 10800, tz=UTC)
        ],
        "open": [1.0, 1.1],
        "high": [1.2, 1.3],
        "low": [0.9, 1.0],
        "close": [1.1, 1.2],
        "tick_volume": [10, 20]
    })
    
    canonical_file = tmp_path / "fake_canonical.parquet"
    df_canonical.to_parquet(canonical_file)
    
    profile = get_metaquotes_demo_phase1_profile()
    
    # 1. Passes with correct +3 profile
    start_ts = datetime.fromtimestamp(raw_time - 10800, tz=UTC)
    end_ts = datetime.fromtimestamp(raw_time + 120 - 10800, tz=UTC)
    verify_raw_canonical_equivalence([raw_file], canonical_file, profile, start_ts, end_ts)
    
    # 2. Fails when the offset is wrong (e.g. +2 profile)
    wrong_profile = TimeProfile(
        profile_id="wrong", broker="x", server="y", symbol="z", source_time_basis="UTC",
        periods=[OffsetPeriod(effective_from=None, effective_to=None, offset_hours=2.0)]
    )
    with pytest.raises(AssertionError):
        verify_raw_canonical_equivalence([raw_file], canonical_file, wrong_profile, start_ts, end_ts)
        
    # 3. Fails when raw timestamp content differs
    df_raw_bad = df_raw.copy()
    df_raw_bad.loc[0, "time"] = raw_time + 1
    df_raw_bad.to_parquet(raw_file)
    with pytest.raises(AssertionError):
        verify_raw_canonical_equivalence([raw_file], canonical_file, profile, start_ts, end_ts)

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
