from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from app.domain.models import DataState
from app.features.core import (
    compute_baseline_features,
    compute_feature_fingerprint,
    resample_bars,
    validate_utc_timestamps,
)


def get_synthetic_data(num_bars=30, start_ts=None):
    if start_ts is None:
        start_ts = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    data = []
    for i in range(num_bars):
        data.append({
            'timestamp': start_ts + timedelta(minutes=i),
            'symbol': 'EURUSD',
            'timeframe': 'M1',
            'open': 1.0 + i*0.001,
            'high': 1.0 + i*0.001 + 0.0005,
            'low': 1.0 + i*0.001 - 0.0005,
            'close': 1.0 + i*0.001 + 0.0002,
            'tick_volume': 100 + i,
            'spread': 2 + (i % 3),
            'real_volume': 0
        })
    return pd.DataFrame(data)

def test_utc_enforcement():
    df = get_synthetic_data(5)
    df['timestamp'] = df['timestamp'].dt.tz_localize(None) # Make naive
    
    with pytest.raises(ValueError, match="Naive timestamps are not permitted"):
        validate_utc_timestamps(df)
        
    # Test normalization of aware non-UTC
    from zoneinfo import ZoneInfo
    df['timestamp'] = df['timestamp'].dt.tz_localize(ZoneInfo('America/New_York'))
    df_utc = validate_utc_timestamps(df)
    assert str(df_utc['timestamp'].dt.tz) == 'UTC'
    assert df_utc['timestamp'].iloc[0] == df['timestamp'].iloc[0] # Identical absolute time

def test_baseline_features_warmup_and_formulas():
    df = get_synthetic_data(30)
    features = compute_baseline_features(df)
    
    assert features['data_state'].iloc[0] == DataState.OBSERVED
    
    # 20-period rolling means 21 bars needed (because ret_1 itself needs 1 bar)
    # The first valid row should be at index 20
    assert not features['is_valid'].iloc[0]
    assert not features['is_valid'].iloc[19]
    assert features['is_valid'].iloc[20]
    assert features['is_valid'].iloc[29]
    
    assert pd.isna(features['vol_20'].iloc[19])
    assert not pd.isna(features['vol_20'].iloc[20])
    
    c1 = df['close'].iloc[1]
    c0 = df['close'].iloc[0]
    expected_ret_1 = np.log(c1 / c0)
    assert np.isclose(features['ret_1'].iloc[1], expected_ret_1)

def test_feature_gap_handling():
    df1 = get_synthetic_data(21)
    df2 = get_synthetic_data(21, start_ts=datetime(2026, 1, 1, 2, 0, tzinfo=UTC)) # gap of >1h
    df = pd.concat([df1, df2]).reset_index(drop=True)
    
    features = compute_baseline_features(df)
    
    # Index 20 is valid (last of block 1)
    assert features['is_valid'].iloc[20]
    
    # Index 21 is start of block 2. Must be invalid!
    assert not features['is_valid'].iloc[21]
    # And 20 bars later (index 41), it becomes valid again
    assert not features['is_valid'].iloc[40]
    assert features['is_valid'].iloc[41]

def test_causality_strict():
    # Changing input strictly after t must not change anything at or before t.
    df = get_synthetic_data(50)
    features_original = compute_baseline_features(df)
    
    for cutoff in [5, 25, 45]:
        df_altered = df.copy()
        df_altered.loc[cutoff+1:, 'close'] *= 1.5
        df_altered.loc[cutoff+1:, 'high'] *= 1.5
        df_altered.loc[cutoff+1:, 'tick_volume'] += 100
        
        features_altered = compute_baseline_features(df_altered)
        
        pd.testing.assert_frame_equal(
            features_original.iloc[:cutoff+1],
            features_altered.iloc[:cutoff+1]
        )
        assert not np.isclose(features_original['ret_1'].iloc[cutoff+1], features_altered['ret_1'].iloc[cutoff+1])

def test_resampling_rules():
    # 1. Normal 5-min aggregation
    df = get_synthetic_data(10)
    res = resample_bars(df, 'M5')
    assert len(res) == 2
    assert res['data_state'].iloc[0] == DataState.OBSERVED
    assert res['data_state'].iloc[1] == DataState.OBSERVED
    assert res['spread'].iloc[0] == df['spread'].iloc[:5].max()
    assert res['tick_volume'].iloc[0] == df['tick_volume'].iloc[:5].sum()
    
    # 2. Incomplete final bucket
    df2 = get_synthetic_data(8)
    res2 = resample_bars(df2, 'M5')
    assert len(res2) == 2
    assert res2['data_state'].iloc[0] == DataState.OBSERVED
    assert res2['data_state'].iloc[1] == DataState.INVALID # incomplete
    
    # 3. Internal missing M1 bar
    df3 = get_synthetic_data(5)
    df3 = df3.drop(2).reset_index(drop=True) # drop middle bar
    res3 = resample_bars(df3, 'M5')
    assert res3['data_state'].iloc[0] == DataState.INVALID
    
    # 4. Session boundary (Gap > 1min)
    df_sess1 = get_synthetic_data(3)
    df_sess2 = get_synthetic_data(3, start_ts=datetime(2026, 1, 1, 1, 0, tzinfo=UTC))
    df4 = pd.concat([df_sess1, df_sess2]).reset_index(drop=True)
    res4 = resample_bars(df4, 'M5')
    # Because they are in different sessions and incomplete, both output bars should be INVALID
    assert res4['data_state'].iloc[0] == DataState.INVALID
    assert res4['data_state'].iloc[1] == DataState.INVALID

def test_fingerprint_determinism():
    df1 = get_synthetic_data(25)
    f1 = compute_baseline_features(df1)
    meta = {"source_dataset_hash": "abc", "transformation_version": "1.0"}
    
    h1 = compute_feature_fingerprint(f1, meta)
    
    # Column reordering does not change hash
    f_shuffled = f1[np.random.permutation(f1.columns)]
    assert compute_feature_fingerprint(f_shuffled, meta) == h1
    
    # Row reordering does not change hash
    f_rev = f1.iloc[::-1]
    assert compute_feature_fingerprint(f_rev, meta) == h1
    
    # Changing metadata changes hash
    meta2 = {"source_dataset_hash": "def", "transformation_version": "1.0"}
    assert compute_feature_fingerprint(f1, meta2) != h1
    
    # Changing data changes hash
    f2 = f1.copy()
    f2.loc[20, 'ret_1'] = 0.99
    assert compute_feature_fingerprint(f2, meta) != h1
