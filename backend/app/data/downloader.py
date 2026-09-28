import datetime

import pandas as pd
from pydantic import BaseModel

from app.data.catalog import DatasetCatalog
from app.data.coverage import DataCalendar
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

def diagnose_missing_bars(
    provider: DataProvider,
    symbol: str,
    missing_timestamps: list[datetime.datetime]
) -> list[dict]:
    results = []
    for m_ts in missing_timestamps:
        end_m = m_ts + datetime.timedelta(minutes=1)
        ticks = provider.fetch_ticks(symbol, m_ts, end_m)
        ticks = ticks[(ticks['timestamp'] >= m_ts) & (ticks['timestamp'] < end_m)]
        tc = len(ticks)
        first_t = ticks['timestamp'].min() if tc > 0 else None
        last_t = ticks['timestamp'].max() if tc > 0 else None
        cls = "NO_TICKS" if tc == 0 else "TICKS_PRESENT_BAR_MISSING"
        results.append({
            "minute_start": m_ts,
            "minute_end": end_m,
            "tick_count": tc,
            "first_tick_utc": first_t,
            "last_tick_utc": last_t,
            "classification": cls
        })
    return results

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
                # Validate chunk schema
                validate_dataframe(df_chunk, expected_symbol=symbol, expected_timeframe=timeframe)
                # Save raw chunk to disk and free memory
                raw_path = self.dataset_manager.save_raw(df_chunk, "mt5", symbol, timeframe)
                chunk_paths.append((raw_path, current_start, current_end))
                
            current_start = current_end
            
        if not chunk_paths:
            raise ValueError("No data returned for entire range")
            
        # Assemble canonical from validated chunks on disk
        # TODO/ADR: For production multi-year ingestion, move to partitioned Parquet and streaming merge instead of pd.concat
        df_list = []
        for p, c_start, c_end in chunk_paths:
            df_p = pd.read_parquet(p)
            # Normalize MT5 inclusive ranges to requested half-open canonical interval [c_start, c_end)
            df_p = df_p[(df_p['timestamp'] >= c_start) & (df_p['timestamp'] < c_end)]
            df_list.append(df_p)
            
        df_full = pd.concat(df_list, ignore_index=True)
        
        # Deduplicate and sort
        initial_len = len(df_full)
        df_full = df_full.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
        duplicates_count = initial_len - len(df_full)
        
        # Gap report
        gap_report = analyze_gaps(df_full, timeframe, start, end, self.calendar)
        
        # Evaluate coverage
        from app.data.coverage import evaluate_coverage
        coverage_status, _expected_timestamps = evaluate_coverage(df_full, start, end, timeframe, self.calendar)
        
        quality_status = "PASS"
        if coverage_status != "FULL":
            quality_status = "FAIL"
            
        if gap_report.unexpected_missing_bars > 0:
            quality_status = "FAIL"
            
        from typing import Literal, cast
        
        quality_report = DataQualityReport(
            coverage_status=cast(Literal["FULL", "PARTIAL", "EMPTY"], coverage_status),
            expected_bars=gap_report.expected_bars,
            observed_bars=gap_report.observed_bars,
            unexpected_missing_bars=gap_report.unexpected_missing_bars,
            known_closure_bars=gap_report.known_closures_bars,
            duplicate_bars=int(duplicates_count),
            quality_status=cast(Literal["PASS", "WARNING", "FAIL"], quality_status)
        )
        
        # --- DIAGNOSTIC ---
        if timeframe == "M1" and quality_report.unexpected_missing_bars > 0:
            df_ts = set(df_full['timestamp'].dt.to_pydatetime()) if not df_full.empty else set()
            missing_ts = [ts for ts in _expected_timestamps if ts not in df_ts]
            print(f"DIAGNOSTIC: Missing M1 timestamps: {missing_ts}")
            diag_results = diagnose_missing_bars(self.provider, symbol, missing_ts)
            for res in diag_results:
                print(f"DIAGNOSTIC GAP: minute_start={res['minute_start']} minute_end={res['minute_end']} tick_count={res['tick_count']} first_tick_utc={res['first_tick_utc']} last_tick_utc={res['last_tick_utc']} classification={res['classification']}")
        # ------------------
        
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
