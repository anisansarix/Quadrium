import hashlib
import json
from typing import Any

import numpy as np
import pandas as pd

from app.domain.models import DataState

# Canonical Timeframe definitions to exact minutes
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
        raise ValueError("Naive timestamps are not permitted. Must be timezone-aware.")
    
    if str(df[col].dt.tz) != 'UTC':
        df = df.copy()
        df[col] = df[col].dt.tz_convert('UTC')
        
    return df

def compute_feature_fingerprint(df: pd.DataFrame, manifest_dict: dict[str, Any]) -> str:
    """
    Fingerprinting that ensures deterministic hash.
    Reordering columns or rows does not change the hash.
    Changing lineage changes the hash.
    """
    df_clean = df.copy()
    
    # 1. Reject naive, normalize to UTC
    df_clean = validate_utc_timestamps(df_clean)
        
    # 2. Sort rows by timestamp
    df_clean = df_clean.sort_values(by="timestamp").reset_index(drop=True)
    
    # 3. Sort columns deterministically
    expected_cols = sorted(df_clean.columns)
    df_clean = df_clean[expected_cols]
    
    # 4. Standardize dtypes
    for col in df_clean.columns:
        if col == "timestamp":
            continue
        if pd.api.types.is_float_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].astype('float64')
        elif pd.api.types.is_integer_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].astype('int64')
        elif pd.api.types.is_bool_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].astype('bool')

    import io
    buf = io.BytesIO()
    df_clean.to_parquet(buf, index=False)
    
    hasher = hashlib.sha256()
    
    # Canonicalize metadata serialization
    serialized_meta = json.dumps(manifest_dict, sort_keys=True)
    hasher.update(serialized_meta.encode('utf-8'))
    hasher.update(buf.getvalue())
    return hasher.hexdigest()

def mark_data_state(df: pd.DataFrame, timeframe_minutes: int) -> pd.DataFrame:
    """Assigns OBSERVED, SOURCE_SPARSE, or INVALID states to rows based on canonical definition."""
    df = df.copy()
    
    df['data_state'] = DataState.OBSERVED
    df.loc[df['tick_volume'] == 0, 'data_state'] = DataState.SOURCE_SPARSE
    
    # Identify gaps. If time to previous row > timeframe_minutes, this row broke contiguity.
    # We don't mark this row as INVALID necessarily (it might be the first row of a new valid block),
    # but any missing rows conceptually represent an INVALID gap.
    # For computation, we need a block_id to prevent rolling across gaps.
    diffs = df['timestamp'].diff().dt.total_seconds() / 60.0
    
    # If the gap > exact timeframe minutes, a new block begins.
    # We assume the dataframe only contains rows that exist.
    is_gap = diffs > timeframe_minutes
    df['block_id'] = is_gap.cumsum().fillna(0).astype(int)
    
    return df

def resample_bars(df: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
    """
    Deterministic resampling of canonical market bars.
    Strictly enforcing complete buckets and cross-session prohibition.
    """
    if df.empty:
        return df
        
    df = df.copy()
    df = validate_utc_timestamps(df)
    
    if target_timeframe not in TIMEFRAME_MINUTES:
        raise ValueError(f"Unknown target timeframe {target_timeframe}")
        
    target_minutes = TIMEFRAME_MINUTES[target_timeframe]
    
    if 'timeframe' in df.columns:
        source_tf = df['timeframe'].iloc[0]
        if source_tf not in TIMEFRAME_MINUTES:
            raise ValueError(f"Unknown source timeframe {source_tf}")
        source_minutes = TIMEFRAME_MINUTES[source_tf]
    else:
        source_minutes = 1 # Assume M1
        
    expected_count = target_minutes // source_minutes
    
    rule = f"{target_minutes}min"
    
    df = df.set_index('timestamp')
    
    # Detect session gaps to avoid aggregating across them
    diffs = df.index.to_series().diff().dt.total_seconds() / 60.0
    # A gap > source_minutes means a break in contiguity (session break or missing data)
    session_id = (diffs > source_minutes).cumsum().fillna(0)
    df['session_id'] = session_id
    
    # Resample per session to strictly prevent cross-session aggregation
    resampled_list = []
    
    for _, group in df.groupby('session_id'):
        resampled_group = group.resample(rule).agg({
            'symbol': 'first',
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'tick_volume': 'sum',
            'spread': 'max', # conservative explicit policy
            'real_volume': 'sum',
            'session_id': 'count' # Used to count underlying bars
        })
        resampled_list.append(resampled_group)
        
    if not resampled_list:
        return pd.DataFrame()
        
    resampled = pd.concat(resampled_list).sort_index()
    
    resampled = resampled.dropna(subset=['open'])
    
    resampled['timeframe'] = target_timeframe
    
    resampled = resampled.reset_index()
    
    # Incomplete bar policy
    resampled['data_state'] = DataState.OBSERVED
    resampled.loc[resampled['tick_volume'] == 0, 'data_state'] = DataState.SOURCE_SPARSE
    
    # If the bucket doesn't have the exact expected count, it's incomplete and therefore INVALID.
    incomplete_mask = resampled['session_id'] != expected_count
    resampled.loc[incomplete_mask, 'data_state'] = DataState.INVALID
    
    # Cleanup internal columns
    resampled = resampled.drop(columns=['session_id'])
    
    return resampled

def compute_baseline_features(df: pd.DataFrame) -> pd.DataFrame:
    """Computes Phase 2 baseline features with strict causality, warmup, and gap validity handling."""
    if df.empty:
        return pd.DataFrame()
        
    df = df.copy()
    df = validate_utc_timestamps(df)
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    source_tf = df['timeframe'].iloc[0] if 'timeframe' in df.columns else 'M1'
    tf_minutes = TIMEFRAME_MINUTES.get(source_tf, 1)
    
    df = mark_data_state(df, tf_minutes)
    
    # We group by block_id to prevent rolling features from crossing INVALID gaps
    grouped = df.groupby('block_id')
    
    # 1. ret_1
    df['ret_1'] = grouped['close'].transform(lambda x: np.log(x / x.shift(1)))
    
    # 2. ret_simple
    df['ret_simple'] = grouped['close'].transform(lambda x: x.pct_change(1))
    
    # 3. range_pct
    df['range_pct'] = (df['high'] - df['low']) / df['open']
    
    # 4. tr
    prev_close = grouped['close'].shift(1)
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            np.abs(df['high'] - prev_close),
            np.abs(df['low'] - prev_close)
        )
    )
    
    # 5. vol_20 (Rolling volatility, 20-period standard deviation of ret_1)
    df['vol_20'] = grouped['ret_1'].transform(lambda x: x.rolling(window=20, min_periods=20).std())
    
    # 6. dist_ma_20
    ma_20 = grouped['close'].transform(lambda x: x.rolling(window=20, min_periods=20).mean())
    df['dist_ma_20'] = (df['close'] - ma_20) / ma_20
    
    # 7. tick_vol_change
    df['tick_vol_change'] = grouped['tick_volume'].transform(lambda x: x.pct_change(1))
    
    # 8. spread
    df['spread_level'] = df['spread']
    
    # 9. spread_delta
    df['spread_delta'] = grouped['spread'].transform(lambda x: x - x.shift(1))
    
    # is_valid requires all rolling features to be fully warmed up and valid,
    # AND the current row must not be explicitly INVALID.
    df['is_valid'] = (
        df['vol_20'].notna() & 
        df['dist_ma_20'].notna() &
        df['tr'].notna() &
        df['tick_vol_change'].notna() &
        (df['data_state'] != DataState.INVALID)
    )
    
    feature_cols = [
        'ret_1', 'ret_simple', 'range_pct', 'tr', 'vol_20', 
        'dist_ma_20', 'tick_vol_change', 'spread_level', 'spread_delta'
    ]
    
    out_cols = ['timestamp', 'symbol', 'timeframe', 'data_state', 'is_valid'] + feature_cols
    return df[out_cols]
