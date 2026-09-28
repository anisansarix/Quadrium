import duckdb
from pathlib import Path
from app.domain.models import DatasetManifest

class DatasetCatalog:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = duckdb.connect(str(self.db_path))
        self._init_db()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id VARCHAR PRIMARY KEY,
                source VARCHAR,
                broker VARCHAR,
                symbol VARCHAR,
                timeframe VARCHAR,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                row_count BIGINT,
                dataset_hash VARCHAR,
                schema_version VARCHAR,
                source_metadata_hash VARCHAR,
                path VARCHAR,
                created_at TIMESTAMP
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS dataset_parts (
                part_id VARCHAR PRIMARY KEY,
                dataset_id VARCHAR,
                part_index INTEGER,
                path VARCHAR
            )
        """)

    def register_dataset(self, manifest: DatasetManifest, parquet_path: Path):
        self.conn.execute("""
            INSERT INTO datasets (
                dataset_id, source, broker, symbol, timeframe, start_time, end_time, 
                row_count, dataset_hash, schema_version, source_metadata_hash, path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            manifest.dataset_id,
            manifest.source,
            manifest.broker,
            manifest.symbol,
            manifest.timeframe,
            manifest.timestamp_start.replace(tzinfo=None),
            manifest.timestamp_end.replace(tzinfo=None),
            manifest.row_count,
            manifest.dataset_hash,
            manifest.schema_version,
            manifest.source_metadata_hash,
            str(parquet_path),
            manifest.fetch_timestamp.replace(tzinfo=None)
        ))

    def query_datasets(self, symbol: str | None = None, timeframe: str | None = None) -> list[dict]:
        query = "SELECT * FROM datasets WHERE 1=1"
        params = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)
            
        return self.conn.execute(query, params).df().to_dict(orient="records")

    def lookup_by_hash(self, dataset_hash: str) -> list[dict]:
        return self.conn.execute("SELECT * FROM datasets WHERE dataset_hash = ?", (dataset_hash,)).df().to_dict(orient="records")

    def lookup_by_symbol(self, symbol: str) -> list[dict]:
        return self.query_datasets(symbol=symbol)
        
    def lookup_by_timeframe(self, timeframe: str) -> list[dict]:
        return self.query_datasets(timeframe=timeframe)

    def get_dataset_path(self, dataset_hash: str) -> str | None:
        res = self.conn.execute("SELECT path FROM datasets WHERE dataset_hash = ?", (dataset_hash,)).fetchone()
        return res[0] if res else None
