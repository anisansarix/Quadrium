import datetime

import pandas as pd
from pydantic import BaseModel

from app.data.catalog import DatasetCatalog
from app.data.datasets import DatasetManager
from app.data.gaps import GapReport, analyze_gaps
from app.data.providers.base import DataProvider
from app.data.quality import DataQualityReport
from app.data.validation import validate_dataframe
from app.domain.models import DatasetManifest


class DatasetArtifact(BaseModel):
    dataset_id: str
    dataset_hash: str
    manifest: DatasetManifest
    canonical_path: str
    gap_report: GapReport
    quality_report: DataQualityReport

class MT5Downloader:
    def __init__(self, provider: DataProvider, dataset_manager: DatasetManager, catalog: DatasetCatalog):
        self.provider = provider
        self.dataset_manager = dataset_manager
        self.catalog = catalog
        
    def download_bars(
        self, 
        symbol: str, 
        timeframe: str, 
        start: datetime.datetime, 
        end: datetime.datetime, 
        chunk_days: int = 30
    ) -> DatasetArtifact:
        
        current_start = start
        chunk_paths = []
        
        while current_start < end:
            current_end = min(current_start + datetime.timedelta(days=chunk_days), end)
            
            # Fetch
            df_chunk = self.provider.fetch_bars(symbol, timeframe, current_start, current_end)
            if not df_chunk.empty:
                # Validate chunk schema
                validate_dataframe(df_chunk, expected_symbol=symbol, expected_timeframe=timeframe)
                # Save raw chunk to disk and free memory
                raw_path = self.dataset_manager.save_raw(df_chunk, "mt5", symbol, timeframe)
                chunk_paths.append(raw_path)
                
            current_start = current_end
            
        if not chunk_paths:
            raise ValueError("No data returned for entire range")
            
        # Assemble canonical from validated chunks on disk
        # TODO/ADR: For production multi-year ingestion, move to partitioned Parquet and streaming merge instead of pd.concat
        df_full = pd.concat([pd.read_parquet(p) for p in chunk_paths], ignore_index=True)
        
        # Deduplicate and sort
        initial_len = len(df_full)
        df_full = df_full.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
        duplicates_count = initial_len - len(df_full)
        
        # Gap report
        gap_report = analyze_gaps(df_full, timeframe, start, end)
        
        # Evaluate coverage
        from app.data.coverage import evaluate_coverage
        coverage_status, _expected_timestamps = evaluate_coverage(df_full, start, end, timeframe)
        
        quality_status = "PASS"
        if coverage_status != "FULL":
            quality_status = "FAIL"
            
        if gap_report.unexpected_missing_bars > 0:
            quality_status = "FAIL"
            
        from typing import cast
        from typing import Literal
        
        quality_report = DataQualityReport(
            coverage_status=cast(Literal["FULL", "PARTIAL", "EMPTY"], coverage_status),
            expected_bars=gap_report.expected_bars,
            observed_bars=gap_report.observed_bars,
            unexpected_missing_bars=gap_report.unexpected_missing_bars,
            known_closure_bars=gap_report.known_closures_bars,
            duplicate_bars=int(duplicates_count),
            invalid_rows=0, # Assuming schema validated
            quality_status=cast(Literal["PASS", "WARNING", "FAIL"], quality_status)
        )
        
        if quality_status == "FAIL":
            raise ValueError(f"Dataset ingestion failed quality checks: {quality_report.model_dump_json()}")
            
        # Source metadata
        spec = self.provider.get_instrument_spec(symbol)
        broker_meta = self.provider.get_broker_metadata()
        
        source_metadata = {
            "broker_metadata": broker_meta,
            "instrument_spec": spec.model_dump()
        }
        
        # Rewrite canonical
        manifest = self.dataset_manager.save_canonical(
            df=df_full,
            source="mt5",
            broker=broker_meta.get("broker", "unknown"),
            symbol=symbol,
            timeframe=timeframe,
            source_metadata=source_metadata
        )
        
        canonical_path = self.dataset_manager.canonical_dir / f"{manifest.dataset_id}.parquet"
        self.catalog.register_dataset(manifest, canonical_path)
        
        return DatasetArtifact(
            dataset_id=manifest.dataset_id,
            dataset_hash=manifest.dataset_hash,
            manifest=manifest,
            canonical_path=str(canonical_path),
            gap_report=gap_report,
            quality_report=quality_report
        )
