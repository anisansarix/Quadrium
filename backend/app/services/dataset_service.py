import json
import uuid
from typing import Any

import pandas as pd

from app.config import settings
from app.core.database import get_duckdb
from app.core.exceptions import DataError
from app.core.logging import get_logger
from app.services.feature_service import FeatureService

log = get_logger(__name__)


class DatasetService:
    """
    Service for creating, versioning, and cataloging processed datasets.
    """

    @classmethod
    def create_dataset(
        cls, raw_data_id: str, version: str, features: list[str]
    ) -> str:
        """
        Create a processed dataset from a raw data source by applying features.
        
        Args:
            raw_data_id: ID of the raw data in market_data_catalog
            version: Version string for the dataset
            features: List of feature names to apply
            
        Returns:
            The dataset catalog entry ID.
        """
        log.info("Creating dataset", raw_id=raw_data_id, version=version, features=features)

        conn = get_duckdb()

        # 1. Fetch raw data metadata
        raw_rows = conn.execute(
            "SELECT * FROM market_data_catalog WHERE id = ?", [raw_data_id]
        ).fetchall()

        if not raw_rows:
            raise DataError(f"Raw data with ID {raw_data_id} not found.")

        raw_meta = dict(zip([desc[0] for desc in conn.description], raw_rows[0]))

        instrument = raw_meta["instrument"]
        timeframe = raw_meta["timeframe"]
        rel_path = raw_meta["file_path"]

        # 2. Load raw parquet
        raw_path = settings.resolve_path("data") / rel_path
        if not raw_path.exists():
            raise DataError(f"Raw data file not found at {raw_path}")

        try:
            df = pd.read_parquet(raw_path)
        except Exception as e:
            log.error("Failed to load raw parquet", path=str(raw_path), error=str(e))
            raise DataError(f"Failed to load raw data: {e}")

        # 3. Apply features
        df_processed = FeatureService.apply_features(df, features)

        if df_processed.empty:
            raise DataError("Processed dataset is empty after feature engineering and dropping NaNs.")

        # 4. Save processed dataset
        processed_dir = settings.resolve_path(settings.data_processed_dir) / version
        processed_dir.mkdir(parents=True, exist_ok=True)

        dataset_id = str(uuid.uuid4())
        filename = f"{instrument}_{timeframe}_{dataset_id[:8]}.parquet"
        file_path = processed_dir / filename

        try:
            df_processed.to_parquet(file_path, engine="pyarrow", index=False)
        except Exception as e:
            log.error("Failed to save processed parquet", path=str(file_path), error=str(e))
            raise DataError(f"Failed to save processed data: {e}")

        # 5. Determine new date range and row count after dropping NaNs
        # Assuming there's a 'time' or 'Date' column
        time_col = next((c for c in df_processed.columns if c.lower() in ["time", "date", "timestamp"]), None)
        if time_col:
            date_start = df_processed[time_col].min().date()
            date_end = df_processed[time_col].max().date()
        else:
            date_start = raw_meta["date_start"]
            date_end = raw_meta["date_end"]

        row_count = len(df_processed)

        try:
            rel_processed_path = file_path.relative_to(settings.resolve_path("data"))
        except ValueError:
            rel_processed_path = file_path

        # 6. Register in DuckDB
        features_json = json.dumps(features)

        conn.execute(
            """
            INSERT INTO dataset_catalog 
            (id, version, features, date_start, date_end, instrument, timeframe, parent_raw_id, row_count, file_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                dataset_id,
                version,
                features_json,
                date_start,
                date_end,
                instrument,
                timeframe,
                raw_data_id,
                row_count,
                str(rel_processed_path)
            ]
        )

        log.info("Dataset created and cataloged", dataset_id=dataset_id, rows=row_count)
        return dataset_id

    @classmethod
    def list_datasets(cls, instrument: str | None = None) -> list[dict[str, Any]]:
        """List all cataloged datasets, optionally filtered by instrument."""
        conn = get_duckdb()
        query = "SELECT * FROM dataset_catalog"
        params = []
        if instrument:
            query += " WHERE instrument = ?"
            params.append(instrument.upper())

        query += " ORDER BY created_at DESC"

        df = conn.execute(query, params).df()

        # Convert JSON strings back to lists
        records = df.to_dict(orient="records")
        for r in records:
            if "features" in r and isinstance(r["features"], str):
                try:
                    r["features"] = json.loads(r["features"])
                except json.JSONDecodeError:
                    r["features"] = []

        return records

    @classmethod
    def get_dataset(cls, dataset_id: str) -> dict[str, Any]:
        """Get dataset metadata by ID."""
        conn = get_duckdb()
        rows = conn.execute(
            "SELECT * FROM dataset_catalog WHERE id = ?", [dataset_id]
        ).fetchall()

        if not rows:
            raise DataError(f"Dataset with ID {dataset_id} not found.")

        record = dict(zip([desc[0] for desc in conn.description], rows[0]))
        if "features" in record and isinstance(record["features"], str):
            try:
                record["features"] = json.loads(record["features"])
            except json.JSONDecodeError:
                record["features"] = []
        return record
