import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from app.domain.models import DatasetManifest


def hash_metadata(metadata: dict[str, Any]) -> str:
    serialized = json.dumps(metadata, sort_keys=True)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

def hash_dataframe(df: pd.DataFrame) -> str:
    # Deterministic hash of dataframe contents
    # Sort columns to ensure consistent layout
    df_sorted = df[sorted(df.columns)]
    # Use pandas string representation or convert to parquet bytes in memory
    # A robust way is hashing the parquet serialization
    import io
    buf = io.BytesIO()
    df_sorted.to_parquet(buf, index=False)
    return hashlib.sha256(buf.getvalue()).hexdigest()

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
        filename = f"{source}_{symbol}_{timeframe}_{timestamp_str}.parquet"
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
        dataset_id = str(uuid4())
        filename = f"{dataset_id}.parquet"
        path = self.canonical_dir / filename
        temp_path = path.with_suffix(".tmp")
        
        # Sort and deduplicate incrementally
        df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
        
        # Atomic write
        df.to_parquet(temp_path, index=False)
        temp_path.replace(path)
        
        with open(path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
            
        ds_hash = hash_dataframe(df)
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
