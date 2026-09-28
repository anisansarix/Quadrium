import datetime
from typing import Any, Literal, cast

import pandas as pd
from pydantic import BaseModel

from app.data.catalog import DatasetCatalog
from app.data.coverage import DataCalendar, evaluate_coverage
from app.data.datasets import DatasetManager
from app.data.gap_diagnostics import diagnose_missing_bars
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
    def __init__(self, provider: DataProvider, dataset_manager: DatasetManager, catalog: DatasetCatalog, calendar: "DataCalendar"):
        self.provider = provider
        self.dataset_manager = dataset_manager
        self.catalog = catalog
        self.calendar = calendar
        
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
                # Save raw chunk to disk and free memory
                raw_path = self.dataset_manager.save_raw(df_chunk, "mt5", symbol, timeframe)
                chunk_paths.append((raw_path, current_start, current_end))
                
            current_start = current_end
            
        if not chunk_paths:
            raise ValueError("No data returned for entire range")
            
        df_list = []
        for p, c_start, c_end in chunk_paths:
            df_p = pd.read_parquet(p)
            
            # Canonicalize raw time -> timestamp
            if hasattr(self.provider, '_time_profile') and self.provider._time_profile:
                tp = self.provider._time_profile
                df_p = tp.add_canonical_column(df_p, raw_col='time', new_col='timestamp')
            else:
                # Fallback if no profile is used, assume raw time is UTC epoch (incorrect but safe fallback)
                df_p['timestamp'] = pd.to_datetime(df_p['time'], unit='s', utc=True)
                
            # Now we can filter strictly by canonical UTC!
            df_p = df_p[(df_p['timestamp'] >= c_start) & (df_p['timestamp'] < c_end)]
            df_list.append(df_p)
            
        df_full = pd.concat(df_list, ignore_index=True)
        validate_dataframe(df_full, expected_symbol=symbol, expected_timeframe=timeframe)
        
        initial_len = len(df_full)
        df_full = df_full.sort_values("timestamp")
        duplicates_count = initial_len - len(df_full)
        
        coverage_status, expected_timestamps = evaluate_coverage(df_full, start, end, timeframe, self.calendar)
        
        missing_classifications: dict[datetime.datetime, str] = {}
        if timeframe == "M1":
            df_ts = set(df_full['timestamp'].dt.to_pydatetime()) if not df_full.empty else set()
            missing_ts = [ts for ts in expected_timestamps if ts not in df_ts]
            if missing_ts:
                diag_results = diagnose_missing_bars(self.provider, symbol, missing_ts)
                for res in diag_results:
                    missing_classifications[res.timestamp_start] = res.classification
        
        gap_report = analyze_gaps(df_full, timeframe, start, end, self.calendar, missing_classifications)
        
        if coverage_status == "PARTIAL" and gap_report.unexpected_missing_bars == 0:
            coverage_status = "SPARSE"
            
        if coverage_status == "EMPTY" or coverage_status == "PARTIAL" or gap_report.unexpected_missing_bars > 0 or gap_report.unexpected_extra_bars > 0 or duplicates_count > 0:
            quality_status = "FAIL"
        else:
            quality_status = "PASS"
            
        if coverage_status == "FULL" and gap_report.no_tick_bars > 0:
            coverage_status = "SPARSE"

        quality_report = DataQualityReport(
            coverage_status=cast(Literal["FULL", "SPARSE", "PARTIAL", "EMPTY"], coverage_status),
            expected_bars=gap_report.expected_bars,
            observed_bars=gap_report.observed_bars,
            source_sparse_bars=gap_report.no_tick_bars,
            ticks_present_bar_missing=gap_report.ticks_present_bar_missing,
            unexpected_missing_bars=gap_report.unexpected_missing_bars,
            known_closure_bars=gap_report.known_closure_bars,
            unexpected_extra_bars=gap_report.unexpected_extra_bars,
            duplicate_bars=int(duplicates_count),
            quality_status=cast(Literal["PASS", "WARNING", "FAIL"], quality_status)
        )
        

            
        if quality_status == "FAIL":
            raise ValueError(f"Dataset ingestion failed quality checks:\nQuality: {quality_report.model_dump_json()}\nGap: {gap_report.model_dump_json()}")

        spec = self.provider.get_instrument_spec(symbol)
        broker_meta = self.provider.get_broker_metadata()
        
        source_metadata: dict[str, Any] = {
            "broker_metadata": broker_meta,
            "instrument_spec": spec.model_dump()
        }
        
        if hasattr(self.provider, '_time_profile') and self.provider._time_profile:
            tp = self.provider._time_profile
            source_metadata["source_time_basis"] = tp.source_time_basis
            source_metadata["canonical_time_basis"] = "UTC"
            source_metadata["time_profile_id"] = tp.profile_id
        
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



