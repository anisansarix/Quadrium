from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from app.data.providers.base import DataProvider


class GapClassification(BaseModel):
    timestamp_start: datetime
    timestamp_end: datetime
    tick_count: int
    classification: Literal["NO_TICKS", "TICKS_PRESENT_BAR_MISSING", "KNOWN_SESSION_CLOSURE"]
    first_tick_utc: datetime | None = None
    last_tick_utc: datetime | None = None


def diagnose_missing_bars(
    provider: DataProvider,
    symbol: str,
    missing_timestamps: list[datetime]
) -> list[GapClassification]:
    results = []
    for m_ts in missing_timestamps:
        end_m = m_ts + timedelta(minutes=1)
        ticks = provider.fetch_ticks(symbol, m_ts, end_m)
        if hasattr(provider, '_time_profile') and getattr(provider, '_time_profile', None):
            tp = provider._time_profile
            # For ticks, raw time is 'time_msc' in milliseconds, but wait, the raw df from fetch_ticks has 'time_msc' and 'time'
            ticks = tp.add_canonical_column(ticks, raw_col='time', new_col='timestamp')
        elif 'timestamp' not in ticks.columns and 'time' in ticks.columns:
            import pandas as pd
            ticks['timestamp'] = pd.to_datetime(ticks['time'], unit='s', utc=True)
            
        ticks = ticks[(ticks['timestamp'] >= m_ts) & (ticks['timestamp'] < end_m)]
        tc = len(ticks)
        
        first_t = None
        last_t = None
        if tc > 0:
            first_t = ticks['timestamp'].min()
            # If pd.NaT is returned, make it None
            if str(first_t) == 'NaT':
                first_t = None
            last_t = ticks['timestamp'].max()
            if str(last_t) == 'NaT':
                last_t = None

        cls: Literal["NO_TICKS", "TICKS_PRESENT_BAR_MISSING", "KNOWN_SESSION_CLOSURE"] = "NO_TICKS" if tc == 0 else "TICKS_PRESENT_BAR_MISSING"
        results.append(GapClassification(
            timestamp_start=m_ts,
            timestamp_end=end_m,
            tick_count=tc,
            classification=cls,
            first_tick_utc=first_t.to_pydatetime() if first_t else None,
            last_tick_utc=last_t.to_pydatetime() if last_t else None
        ))
    return results
