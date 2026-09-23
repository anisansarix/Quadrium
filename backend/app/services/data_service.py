import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.database import get_duckdb
from app.core.exceptions import DataError
from app.core.logging import get_logger
from app.services.fetchers.base import DataFetcher
from app.services.fetchers.mt5_fetcher import MT5Fetcher
from app.services.fetchers.yfinance_fetcher import YFinanceFetcher

log = get_logger(__name__)


class DataService:
    """
    Service for acquiring, storing, and cataloging raw market data.
    """

    @classmethod
    async def fetch_and_store(
        cls,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        source: str = "mt5",
    ) -> str:
        """
        Fetch historical data and store it as a Parquet file,
        then register it in the DuckDB catalog.

        Returns:
            The catalog entry ID.
        """
        log.info("Starting data fetch", symbol=symbol, timeframe=timeframe, source=source)

        # 1. Instantiate the fetcher
        fetcher: DataFetcher
        if source.lower() == "mt5":
            fetcher = MT5Fetcher()
        elif source.lower() == "yfinance":
            fetcher = YFinanceFetcher()
        else:
            raise ValueError(f"Unknown data source: {source}")

        # 2. Fetch the data
        try:
            df = await fetcher.fetch_historical_data(symbol, timeframe, start, end)
        except Exception as e:
            log.error("Data fetch failed", error=str(e))
            raise DataError(f"Fetch failed: {e}")

        if df.empty:
            raise DataError(f"No data returned for {symbol} ({timeframe})")

        # Ensure directory exists
        raw_dir = settings.resolve_path(settings.data_raw_dir) / symbol.upper() / timeframe.upper()
        raw_dir.mkdir(parents=True, exist_ok=True)

        # 3. Determine file path and save to Parquet
        # Format: YYYYMMDD_YYYYMMDD.parquet
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        # Use UUID to prevent overwriting if we fetch exact same range multiple times,
        # or we could overwrite. Let's use a unique name.
        catalog_id = str(uuid.uuid4())
        filename = f"{start_str}_{end_str}_{catalog_id[:8]}.parquet"
        file_path = raw_dir / filename

        try:
            # We use pyarrow engine for best compatibility
            df.to_parquet(file_path, engine="pyarrow", index=False)
        except Exception as e:
            log.error("Failed to save parquet", error=str(e), path=str(file_path))
            raise DataError(f"Failed to save data: {e}")

        # 4. Hash the file
        file_hash = cls._hash_file(file_path)

        # 5. Register in DuckDB catalog
        row_count = len(df)
        # Convert absolute path to relative path string from data dir to make it portable
        try:
            rel_path = file_path.relative_to(settings.resolve_path("data"))
        except ValueError:
            rel_path = file_path

        conn = get_duckdb()
        conn.execute(
            """
            INSERT INTO market_data_catalog 
            (id, instrument, timeframe, date_start, date_end, row_count, file_path, file_hash, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                catalog_id,
                symbol.upper(),
                timeframe.upper(),
                start.date(),
                end.date(),
                row_count,
                str(rel_path),
                file_hash,
                source.lower()
            ]
        )

        log.info("Data cataloged successfully", catalog_id=catalog_id, rows=row_count)
        return catalog_id

    @classmethod
    def list_raw_data(cls, instrument: str | None = None) -> list[dict[str, Any]]:
        """List all cataloged raw data, optionally filtered by instrument."""
        conn = get_duckdb()
        query = "SELECT * FROM market_data_catalog"
        params = []
        if instrument:
            query += " WHERE instrument = ?"
            params.append(instrument.upper())

        query += " ORDER BY fetched_at DESC"

        # Convert to dictionary
        df = conn.execute(query, params).df()
        return df.to_dict(orient="records")

    @classmethod
    def _hash_file(cls, path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
