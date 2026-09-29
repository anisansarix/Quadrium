from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest
from app.domain.models import DataState, FeatureLineage, FeatureManifest, FeatureState
from app.features.core import (
    compute_baseline_features,
    compute_feature_fingerprint,
    resample_bars,
    validate_utc_timestamps,
)
from pydantic import ValidationError


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
    df['timestamp'] = df['timestamp'].dt.tz_localize(None)
    with pytest.raises(ValueError, match="Naive timestamps are not permitted"):
        validate_utc_timestamps(df)

    from zoneinfo import ZoneInfo
    df['timestamp'] = df['timestamp'].dt.tz_localize(ZoneInfo('America/New_York'))
    df_utc = validate_utc_timestamps(df)
    assert str(df_utc['timestamp'].dt.tz) == 'UTC'

def test_baseline_features_warmup_and_formulas():
    df = get_synthetic_data(30)
    features = compute_baseline_features(df)

    assert features['data_state'].iloc[0] == DataState.OBSERVED

    assert features['feature_state'].iloc[0] == FeatureState.WARMUP
    assert features['feature_state'].iloc[19] == FeatureState.WARMUP
    assert features['feature_state'].iloc[20] == FeatureState.VALID
    assert features['feature_state'].iloc[29] == FeatureState.VALID

    c1 = df['close'].iloc[1]
    c0 = df['close'].iloc[0]
    expected_ret_1 = np.log(c1 / c0)
    assert np.isclose(features['ret_1'].iloc[1], expected_ret_1)

def test_feature_gap_handling():
    df1 = get_synthetic_data(21)
    df2 = get_synthetic_data(21, start_ts=datetime(2026, 1, 1, 2, 0, tzinfo=UTC))
    df = pd.concat([df1, df2]).reset_index(drop=True)

    features = compute_baseline_features(df)
    assert features['feature_state'].iloc[20] == FeatureState.VALID

    # Gap breaks contiguity. First row after gap is INVALID (not WARMUP).
    assert features['feature_state'].iloc[21] == FeatureState.INVALID
    assert features['feature_state'].iloc[40] == FeatureState.INVALID
    # After rebuilding lookback (20 periods later, index 41), it's VALID again.
    assert features['feature_state'].iloc[41] == FeatureState.VALID

def test_causality_strict():
    df = get_synthetic_data(50)
    features_original = compute_baseline_features(df)
    for cutoff in [5, 25, 45]:
        df_altered = df.copy()
        df_altered.loc[cutoff+1:, 'close'] *= 1.5
        df_altered.loc[cutoff+1:, 'high'] *= 1.5
        features_altered = compute_baseline_features(df_altered)
        pd.testing.assert_frame_equal(features_original.iloc[:cutoff+1], features_altered.iloc[:cutoff+1])

def test_resampling_rules():
    df = get_synthetic_data(10)
    res = resample_bars(df, 'M5')
    assert len(res) == 2
    assert res['data_state'].iloc[0] == DataState.OBSERVED

    df2 = get_synthetic_data(8)
    res2 = resample_bars(df2, 'M5')
    assert res2['data_state'].iloc[1] == DataState.INVALID

    df3 = get_synthetic_data(5)
    df3 = df3.drop(2).reset_index(drop=True)
    res3 = resample_bars(df3, 'M5')
    assert res3['data_state'].iloc[0] == DataState.INVALID

    df_sess1 = get_synthetic_data(3)
    df_sess2 = get_synthetic_data(3, start_ts=datetime(2026, 1, 1, 1, 0, tzinfo=UTC))
    df4 = pd.concat([df_sess1, df_sess2]).reset_index(drop=True)
    res4 = resample_bars(df4, 'M5')
    assert res4['data_state'].iloc[0] == DataState.INVALID
    assert res4['data_state'].iloc[1] == DataState.INVALID

def test_fingerprint_determinism():
    df1 = get_synthetic_data(25)
    f1 = compute_baseline_features(df1)

    meta = FeatureLineage(
        source_dataset_hash="abc",
        symbol="EURUSD",
        source_timeframe="M1",
        feature_timeframe="M1",
        feature_schema_version="1.0",
        transformation_version="1.0",
        configuration_version="1.0"
    )

    h1 = compute_feature_fingerprint(f1, meta)

    f_shuffled = f1[np.random.permutation(f1.columns)]
    assert compute_feature_fingerprint(f_shuffled, meta) == h1

    f_rev = f1.iloc[::-1]
    assert compute_feature_fingerprint(f_rev, meta) == h1

    # Missing lineage field fails via Pydantic
    with pytest.raises(ValidationError):
        FeatureLineage(source_dataset_hash="abc")

def test_duplicate_timestamp_fails():
    df = get_synthetic_data(5)
    df = pd.concat([df, df.iloc[-1:]])
    with pytest.raises(ValueError, match="Duplicate timestamps"):
        validate_utc_timestamps(df)

def test_missing_timeframe_or_column_fails():
    # Fails even if dataframe is empty
    df_empty = pd.DataFrame()
    with pytest.raises(ValueError, match="Missing required canonical column"):
        compute_baseline_features(df_empty)

    df = get_synthetic_data(5)
    df_no_tf = df.drop(columns=['timeframe'])
    with pytest.raises(ValueError, match="Missing required canonical column"):
        resample_bars(df_no_tf, 'M5')

    df_no_close = df.drop(columns=['close'])
    with pytest.raises(ValueError, match="Missing required canonical column"):
        compute_baseline_features(df_no_close)

def test_mixed_symbols_and_timeframes():
    df = get_synthetic_data(5)
    df.loc[0, 'symbol'] = 'GBPUSD'
    with pytest.raises(ValueError, match="Mixed symbols"):
        compute_baseline_features(df)

    df2 = get_synthetic_data(5)
    df2.loc[0, 'timeframe'] = 'M5'
    with pytest.raises(ValueError, match="Mixed timeframes"):
        compute_baseline_features(df2)

def test_invalid_timeframe_combinations():
    df = get_synthetic_data(5)
    df['timeframe'] = 'M5'
    with pytest.raises(ValueError, match="Target timeframe cannot be shorter"):
        resample_bars(df, 'M1')

    with pytest.raises(ValueError, match="Unknown target timeframe"):
        resample_bars(df, 'M3')

def test_manifest_validation():
    with pytest.raises(ValueError, match="Timestamps must be timezone-aware UTC"):
        FeatureManifest(
            feature_dataset_id="1", source_dataset_hash="1", symbol="1", source_timeframe="1", feature_timeframe="1",
            feature_schema_version="1", transformation_version="1", configuration_version="1", feature_fingerprint="1",
            timestamp_start=datetime(2026, 1, 1), # noqa: DTZ001
            timestamp_end=datetime(2026, 1, 2, tzinfo=UTC),
            created_at=datetime(2026, 1, 2, tzinfo=UTC),
            row_count=10, feature_columns=["A"]
        )
