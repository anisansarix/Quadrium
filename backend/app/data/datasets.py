import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.domain.models import DatasetManifest


def hash_metadata(metadata: dict[str, Any]) -> str:
    serialized = json.dumps(metadata, sort_keys=True)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

def hash_dataframe(df: pd.DataFrame, schema_version: str = "1.0") -> str:
    """
    Canonical Dataset Hashing Version 1.0.
    Produces a deterministic SHA-256 hash independent of input row order.
    
    Steps:
    1. Schema validation (implicitly via expected cols)
    2. Normalize dtypes (ensure standard float64/int64/datetime64)
    3. Normalize UTC timestamps
    4. Sort rows by timestamp
    5. Sort columns by canonical schema order
    6. Deterministic serialization (Parquet)
    7. SHA-256
    """
    df_clean = df.copy()
    
    # Normalize UTC timestamps
    if df_clean['timestamp'].dt.tz is None:
        df_clean['timestamp'] = df_clean['timestamp'].dt.tz_localize('UTC')
    else:
        df_clean['timestamp'] = df_clean['timestamp'].dt.tz_convert('UTC')
        
    # Sort rows
    df_clean = df_clean.sort_values(by="timestamp").reset_index(drop=True)
    
    # Sort columns canonically
    bar_cols = ["timestamp", "symbol", "timeframe", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
    tick_cols = ["timestamp", "symbol", "bid", "ask", "last", "volume", "flags"]
    
    if "open" in df_clean.columns:
        expected = [c for c in bar_cols if c in df_clean.columns]
        dataset_type = "bars"
    elif "bid" in df_clean.columns:
        expected = [c for c in tick_cols if c in df_clean.columns]
        dataset_type = "ticks"
    else:
        expected = sorted(df_clean.columns)
        dataset_type = "unknown"
        
    df_clean = df_clean[expected]
    
    # Normalize dtypes
    for col in df_clean.columns:
        if col == "timestamp":
            continue
        if pd.api.types.is_float_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].astype('float64')
        elif pd.api.types.is_integer_dtype(df_clean[col]):
            df_clean[col] = df_clean[col].astype('int64')
    
    import io
    buf = io.BytesIO()
    # Write parquet deterministically without pandas index
    df_clean.to_parquet(buf, index=False)
    
    hasher = hashlib.sha256()
    # Incorporate schema version and dataset metadata into the hash
    symbol = df_clean['symbol'].iloc[0] if 'symbol' in df_clean.columns and not df_clean.empty else 'unknown'
    timeframe = df_clean['timeframe'].iloc[0] if 'timeframe' in df_clean.columns and not df_clean.empty else 'unknown'
    
    hash_algorithm_version = "1.0"
    header = f"V{schema_version}|V{hash_algorithm_version}|{dataset_type}|{symbol}|{timeframe}|"
    hasher.update(header.encode())
    hasher.update(buf.getvalue())
    return hasher.hexdigest()

class DatasetManager:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.raw_dir = base_dir / "raw"
        self.canonical_dir = base_dir / "canonical"
        self.manifest_dir = base_dir / "manifests"
        
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.canonical_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

    def save_raw(self, df: pd.DataFrame, source: str, symbol: str, timeframe: str) -> Path:
        timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        
        # Fast content hash for deduplication/naming without full canonicalization
        import io
        buf = io.BytesIO()
        df.to_parquet(buf, index=False)
        content_hash = hashlib.sha256(buf.getvalue()).hexdigest()[:8]
        
        filename = f"{source}_{symbol}_{timeframe}_{timestamp_str}_{content_hash}.parquet"
        path = self.raw_dir / filename
        temp_path = path.with_suffix(".tmp")
        df.to_parquet(temp_path, index=False)
        temp_path.replace(path)
        return path
        
    def save_canonical(
        self, 
        df: pd.DataFrame, 
        source: str, 
        broker: str, 
        symbol: str, 
        timeframe: str, 
        source_metadata: dict[str, Any],
        schema_version: str = "1.0"
    ) -> DatasetManifest:
        df = df.sort_values("timestamp")
        
        ds_hash = hash_dataframe(df, schema_version)
        
        start_dt = df["timestamp"].min().strftime("%Y%m%d")
        end_dt = df["timestamp"].max().strftime("%Y%m%d")
        dataset_id = f"{source}_{symbol}_{timeframe}_{start_dt}_{end_dt}_{ds_hash[:8]}"
        
        filename = f"{dataset_id}.parquet"
        path = self.canonical_dir / filename
        temp_path = path.with_suffix(".tmp")
        
        # Atomic write
        df.to_parquet(temp_path, index=False)
        temp_path.replace(path)
        
        with open(path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            
        meta_hash = hash_metadata(source_metadata)
        
        manifest = DatasetManifest(
            dataset_id=dataset_id,
            source=source,
            broker=broker,
            symbol=symbol,
            timeframe=timeframe,
            timestamp_start=df["timestamp"].min(),
            timestamp_end=df["timestamp"].max(),
            row_count=len(df),
            schema_version=schema_version,
            file_hash=file_hash,
            dataset_hash=ds_hash,
            source_metadata_hash=meta_hash,
            source_metadata=source_metadata,
            fetch_timestamp=datetime.now(UTC)
        )
        
        manifest_path = self.manifest_dir / f"{dataset_id}.json"
        with open(manifest_path, "w") as f:
            f.write(manifest.model_dump_json(indent=2))
            
        return manifest

    def load_canonical(self, dataset_id: str) -> pd.DataFrame:
        path = self.canonical_dir / f"{dataset_id}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"Dataset {dataset_id} not found")
        return pd.read_parquet(path)
