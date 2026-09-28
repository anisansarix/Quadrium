from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from app.data.datasets import DatasetManager


def test_dataset_hashing_is_deterministic(tmp_path: Path):
    manager = DatasetManager(tmp_path)
    
    # Create a small deterministic dataframe
    df = pd.DataFrame({
        "timestamp": [datetime(2023, 1, 1, 10, 0, tzinfo=UTC)],
        "symbol": ["EURUSD"],
        "timeframe": ["M1"],
        "open": [1.1],
        "high": [1.2],
        "low": [1.0],
        "close": [1.15],
        "tick_volume": [100],
        "spread": [2],
        "real_volume": [100]
    })
    
    meta = {"digits": 5}
    
    manifest1 = manager.save_canonical(df.copy(), "mt5", "broker", "EURUSD", "M1", meta)
    manifest2 = manager.save_canonical(df.copy(), "mt5", "broker", "EURUSD", "M1", meta)
    
    # Hashes should be identical, even though dataset_ids and file_hashes are different
    assert manifest1.dataset_hash == manifest2.dataset_hash
    assert manifest1.source_metadata_hash == manifest2.source_metadata_hash
    assert manifest1.dataset_id == manifest2.dataset_id
    
def test_dataset_catalog(tmp_path: Path):
    from app.data.catalog import DatasetCatalog
    
    manager = DatasetManager(tmp_path)
    catalog = DatasetCatalog(tmp_path / "test.db")
    
    df = pd.DataFrame({
        "timestamp": [datetime(2023, 1, 1, 10, 0, tzinfo=UTC)],
        "symbol": ["EURUSD"],
        "timeframe": ["M1"],
        "open": [1.1],
        "high": [1.2],
        "low": [1.0],
        "close": [1.15],
        "tick_volume": [100],
        "spread": [2],
        "real_volume": [100]
    })
    
    manifest = manager.save_canonical(df, "mt5", "broker", "EURUSD", "M1", {})
    catalog.register_dataset(manifest, manager.canonical_dir / f"{manifest.dataset_id}.parquet")
    
    results = catalog.query_datasets(symbol="EURUSD", timeframe="M1")
    assert len(results) == 1
    assert results[0]["dataset_id"] == manifest.dataset_id


def test_hash_dataframe_is_canonical():
    from datetime import datetime

    import pandas as pd
    from app.data.datasets import hash_dataframe
    
    # 1. Order independence
    df1 = pd.DataFrame({
        'timestamp': [datetime(2023, 1, 1, 10, tzinfo=UTC), datetime(2023, 1, 1, 11, tzinfo=UTC)],
        'symbol': ['EURUSD', 'EURUSD'], 'timeframe': ['M1', 'M1'],
        'open': [1.0, 2.0], 'high': [1.0, 2.0], 'low': [1.0, 2.0], 'close': [1.0, 2.0],
    })
    
    df2 = pd.DataFrame({
        'timestamp': [datetime(2023, 1, 1, 11, tzinfo=UTC), datetime(2023, 1, 1, 10, tzinfo=UTC)],
        'symbol': ['EURUSD', 'EURUSD'], 'timeframe': ['M1', 'M1'],
        'open': [2.0, 1.0], 'high': [2.0, 1.0], 'low': [2.0, 1.0], 'close': [2.0, 1.0],
    })
    
    assert hash_dataframe(df1) == hash_dataframe(df2)
    
    # 2. Value dependence
    df3 = pd.DataFrame({
        'timestamp': [datetime(2023, 1, 1, 10, tzinfo=UTC), datetime(2023, 1, 1, 11, tzinfo=UTC)],
        'symbol': ['EURUSD', 'EURUSD'], 'timeframe': ['M1', 'M1'],
        'open': [1.0, 3.0], 'high': [1.0, 2.0], 'low': [1.0, 2.0], 'close': [1.0, 2.0],
    })
    assert hash_dataframe(df1) != hash_dataframe(df3)
    
    # 3. Schema version dependence
    assert hash_dataframe(df1, schema_version="1.0") != hash_dataframe(df1, schema_version="2.0")

    # 4. Symbol dependence
    df_gbp = df1.copy()
    df_gbp['symbol'] = 'GBPUSD'
    assert hash_dataframe(df1) != hash_dataframe(df_gbp)

    # 5. Timeframe dependence
    df_m5 = df1.copy()
    df_m5['timeframe'] = 'M5'
    assert hash_dataframe(df1) != hash_dataframe(df_m5)

