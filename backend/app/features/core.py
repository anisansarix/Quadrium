import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd

from app.domain.models import DataState, FeatureState

TIMEFRAME_MINUTES = {
    'M1': 1,
    'M5': 5,
    'M15': 15,
    'H1': 60
}

def validate_utc_timestamps(df: pd.DataFrame, col: str = 'timestamp') -> pd.DataFrame:
    """Enforces strict UTC timezone awareness. Fails on naive."""
    if df.empty:
        return df

    if df[col].dt.tz is None:
        raise ValueError("Naive timestamps are not permitted. Must be timezone-aware UTC.")

    if str(df[col].dt.tz) != 'UTC':
        df = df.copy()
        df[col] = df[col].dt.tz_convert('UTC')

    # Reject duplicates
    if df[col].duplicated().any():
        raise ValueError("Duplicate timestamps found in dataset.")

    return df

def compute_feature_fingerprint(df: pd.DataFrame, manifest_dict: dict[str, Any]) -> str:
    df_clean = df.copy()

    # Reject naive, normalize to UTC, reject duplicates
    df_clean = validate_utc_timestamps(df_clean)

    df_clean = df_clean.sort_values(by="timestamp").reset_index(drop=True)
    expected_cols = sorted(df_clean.columns)
    df_clean = df_clean[expected_cols]

    for col in df_clean.columns:
        if col == "timestamp":
            continue
        if pd.api.types.is_float_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].astype('float64')
        elif pd.api.types.is_integer_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].astype('int64')
        elif pd.api.types.is_bool_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].astype('bool')
        elif pd.api.types.is_string_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].astype(str)

    import io
    buf = io.BytesIO()
    df_clean.to_parquet(buf, index=False)

    hasher = hashlib.sha256()
    serialized_meta = json.dumps(manifest_dict, sort_keys=True)
    hasher.update(serialized_meta.encode('utf-8'))
    hasher.update(buf.getvalue())
    return hasher.hexdigest()

def mark_data_state(df: pd.DataFrame, timeframe_minutes: int) -> pd.DataFrame:
    df = df.copy()

    df['data_state'] = DataState.OBSERVED
    df.loc[df['tick_volume'] == 0, 'data_state'] = DataState.SOURCE_SPARSE

    diffs = df['timestamp'].diff().dt.total_seconds() / 60.0
    is_gap = diffs > timeframe_minutes
    df['block_id'] = is_gap.cumsum().fillna(0).astype(int)

    return df

def resample_bars(df: pd.DataFrame, target_timeframe: str, calendar=None) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()

    # Required columns validation
    req_cols = ['timestamp', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']
    for c in req_cols:
        if c not in df.columns:
            raise ValueError(f"Missing required canonical column: {c}")

    df = validate_utc_timestamps(df)

    if target_timeframe not in TIMEFRAME_MINUTES:
        raise ValueError(f"Unknown target timeframe {target_timeframe}")

    target_minutes = TIMEFRAME_MINUTES[target_timeframe]

    source_tf = df['timeframe'].iloc[0]
    if source_tf not in TIMEFRAME_MINUTES:
        raise ValueError(f"Unknown source timeframe {source_tf}")

    source_minutes = TIMEFRAME_MINUTES[source_tf]

    if target_minutes < source_minutes:
        raise ValueError("Target timeframe cannot be shorter than source timeframe.")
    if target_minutes % source_minutes != 0:
        raise ValueError("Target timeframe must be an integer multiple of source timeframe.")

    expected_count = target_minutes // source_minutes
    rule = f"{target_minutes}min"

    df = df.set_index('timestamp')

    # Session boundary vs unexpected gap
    # A gap > source_minutes means a break.
    # If calendar is provided, we could distinguish. But even without it, any gap > source_minutes prevents aggregation.
    # The requirement: "never aggregate across either type of boundary".
    # So we strictly split blocks at any gap > source_minutes.
    diffs = df.index.to_series().diff().dt.total_seconds() / 60.0
    session_id = (diffs > source_minutes).cumsum().fillna(0)
    df['session_id'] = session_id

    resampled_list = []
    for _, group in df.groupby('session_id'):
        resampled_group = group.resample(rule).agg({
            'symbol': 'first',
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'tick_volume': 'sum',
            'spread': 'max',
            'real_volume': 'sum',
            'session_id': 'count'
        })
        resampled_list.append(resampled_group)

    if not resampled_list:
        return pd.DataFrame()

    resampled = pd.concat(resampled_list).sort_index()
    resampled = resampled.dropna(subset=['open'])
    resampled['timeframe'] = target_timeframe
    resampled = resampled.reset_index()

    resampled['data_state'] = DataState.OBSERVED
    resampled.loc[resampled['tick_volume'] == 0, 'data_state'] = DataState.SOURCE_SPARSE

    incomplete_mask = resampled['session_id'] != expected_count
    resampled.loc[incomplete_mask, 'data_state'] = DataState.INVALID

    resampled = resampled.drop(columns=['session_id'])

    return resampled

def compute_baseline_features(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    df = df.copy()

    req_cols = ['timestamp', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume']
    for c in req_cols:
        if c not in df.columns:
            raise ValueError(f"Missing required canonical column: {c}")

    df = validate_utc_timestamps(df)
    df = df.sort_values("timestamp").reset_index(drop=True)

    source_tf = df['timeframe'].iloc[0]
    if source_tf not in TIMEFRAME_MINUTES:
        raise ValueError(f"Unknown source timeframe {source_tf}")

    tf_minutes = TIMEFRAME_MINUTES[source_tf]
    df = mark_data_state(df, tf_minutes)

    grouped = df.groupby('block_id')

    df['ret_1'] = grouped['close'].transform(lambda x: np.log(x / x.shift(1)))
    df['ret_simple'] = grouped['close'].transform(lambda x: x.pct_change(1))
    df['range_pct'] = (df['high'] - df['low']) / df['open']

    prev_close = grouped['close'].shift(1)
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            np.abs(df['high'] - prev_close),
            np.abs(df['low'] - prev_close)
        )
    )

    df['vol_20'] = grouped['ret_1'].transform(lambda x: x.rolling(window=20, min_periods=20).std())

    ma_20 = grouped['close'].transform(lambda x: x.rolling(window=20, min_periods=20).mean())
    df['dist_ma_20'] = (df['close'] - ma_20) / ma_20

    df['tick_vol_change'] = grouped['tick_volume'].transform(lambda x: x.pct_change(1))

    df['spread_level'] = df['spread']
    df['spread_delta'] = grouped['spread'].transform(lambda x: x - x.shift(1))

    # Feature State Logic
    df['feature_state'] = FeatureState.VALID

    # Warmup identification
    # A row is in WARMUP if any required feature is NaN (which pandas naturally sets during warmup across the block_id group)
    is_warmup = (
        df['vol_20'].isna() |
        df['dist_ma_20'].isna() |
        df['tr'].isna() |
        df['tick_vol_change'].isna()
    )

    df.loc[is_warmup, 'feature_state'] = FeatureState.WARMUP

    # Invalid overrides warmup
    df.loc[df['data_state'] == DataState.INVALID, 'feature_state'] = FeatureState.INVALID

    feature_cols = [
        'ret_1', 'ret_simple', 'range_pct', 'tr', 'vol_20',
        'dist_ma_20', 'tick_vol_change', 'spread_level', 'spread_delta'
    ]

    out_cols = ['timestamp', 'symbol', 'timeframe', 'data_state', 'feature_state'] + feature_cols
    return df[out_cols]
