import datetime
from pathlib import Path

import pandas as pd

from app.data.datasets import DatasetManager
from app.data.providers.mt5 import MT5Provider
from app.data.validation import validate_dataframe
from app.data.gaps import analyze_gaps, GapReport


class MT5Downloader:
    def __init__(self, provider: MT5Provider, dataset_manager: DatasetManager):
        self.provider = provider
        self.dataset_manager = dataset_manager
        
    def download_bars(
        self, 
        symbol: str, 
        timeframe: str, 
        start: datetime.datetime, 
        end: datetime.datetime, 
        chunk_days: int = 30
    ) -> tuple[str, GapReport]:
        
        current_start = start
        dfs = []
        
        while current_start < end:
            current_end = min(current_start + datetime.timedelta(days=chunk_days), end)
            
            # Fetch
            df_chunk = self.provider.fetch_bars(symbol, timeframe, current_start, current_end)
            if not df_chunk.empty:
                dfs.append(df_chunk)
                
                # Save raw
                self.dataset_manager.save_raw(df_chunk, "mt5", symbol, timeframe)
                
            current_start = current_end
            
        if not dfs:
            raise ValueError("No data returned for entire range")
            
        df_full = pd.concat(dfs, ignore_index=True)
        
        # Deduplicate and sort
        df_full = df_full.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
        
        # Validate
        validate_dataframe(df_full, expected_symbol=symbol, expected_timeframe=timeframe)
        
        # Source metadata
        spec = self.provider.get_instrument_spec(symbol)
        source_metadata = {
            "broker_symbol": spec.broker_symbol,
            "digits": spec.digits,
            "tick_size": spec.tick_size
        }
        
        # Gap report
        gap_report = analyze_gaps(df_full, timeframe)
        
        # Rewrite canonical
        manifest = self.dataset_manager.save_canonical(
            df=df_full,
            source="mt5",
            broker="unknown", # We can fetch broker name if we wanted
            symbol=symbol,
            timeframe=timeframe,
            source_metadata=source_metadata
        )
        
        return manifest.dataset_id, gap_report
