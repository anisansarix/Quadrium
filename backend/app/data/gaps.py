from datetime import datetime

import pandas as pd
from pydantic import BaseModel

from app.data.coverage import DataCalendar


class MissingInterval(BaseModel):
    start: datetime
    end: datetime
    bars_missing: int
    is_known_closure: bool

class ExtraInterval(BaseModel):
    start: datetime
    end: datetime
    bars_extra: int

class GapReport(BaseModel):
    expected_bars: int
    observed_bars: int
    missing_bars: int
    no_tick_bars: int
    ticks_present_bar_missing: int
    known_closure_bars: int
    missing_intervals: list[MissingInterval]
    extra_intervals: list[ExtraInterval]
    unexpected_missing_bars: int
    unexpected_extra_bars: int

def analyze_gaps(df: pd.DataFrame, timeframe: str, start: datetime, end: datetime, calendar: DataCalendar, missing_classifications: dict[datetime, str] | None = None) -> GapReport:
    if missing_classifications is None:
        missing_classifications = {}
        
    freq_map = {"M1": "1min", "M5": "5min"}
    if timeframe not in freq_map:
        return GapReport(expected_bars=0, observed_bars=0, missing_bars=0, no_tick_bars=0, ticks_present_bar_missing=0, known_closure_bars=0, missing_intervals=[], extra_intervals=[], unexpected_missing_bars=0, unexpected_extra_bars=0)
        
    freq = freq_map[timeframe]
    expected_weekdays = calendar.get_expected_bars(start, end, freq)
    
    expected_bars_count = len(expected_weekdays)
    observed_bars = len(df)
    
    df_ts = set(df['timestamp'].dt.to_pydatetime()) if not df.empty and 'timestamp' in df.columns else set()
    missing = sorted([ts for ts in expected_weekdays if ts not in df_ts])
    missing_bars = len(missing)
    
    no_tick_bars = 0
    ticks_present_bar_missing = 0
    
    for ts in missing:
        cls = missing_classifications.get(ts)
        if cls == "NO_TICKS":
            no_tick_bars += 1
        else:
            # Unclassified or TICKS_PRESENT_BAR_MISSING
            ticks_present_bar_missing += 1
    

    missing_intervals = []
    if missing:
        current_start = missing[0]
        current_prev = missing[0]
        count = 1
        delta = pd.Timedelta(freq)
        
        for ts in missing[1:]:
            if ts == current_prev + delta:
                current_prev = ts
                count += 1
            else:
                missing_intervals.append(MissingInterval(start=current_start, end=current_prev, bars_missing=count, is_known_closure=False))
                current_start = ts
                current_prev = ts
                count = 1
        missing_intervals.append(MissingInterval(start=current_start, end=current_prev, bars_missing=count, is_known_closure=False))

    expected_set = set(expected_weekdays)
    extra = sorted([ts for ts in df_ts if ts not in expected_set])
    unexpected_extra_bars = len(extra)

    extra_intervals = []
    if extra:
        current_start = extra[0]
        current_prev = extra[0]
        count = 1
        delta = pd.Timedelta(freq)
        
        for ts in extra[1:]:
            if ts == current_prev + delta:
                current_prev = ts
                count += 1
            else:
                extra_intervals.append(ExtraInterval(start=current_start, end=current_prev, bars_extra=count))
                current_start = ts
                current_prev = ts
                count = 1
        extra_intervals.append(ExtraInterval(start=current_start, end=current_prev, bars_extra=count))
        
    return GapReport(
        expected_bars=expected_bars_count,
        observed_bars=observed_bars,
        missing_bars=missing_bars,
        no_tick_bars=no_tick_bars,
        ticks_present_bar_missing=ticks_present_bar_missing,
        known_closure_bars=0,
        missing_intervals=missing_intervals,
        extra_intervals=extra_intervals,
        unexpected_missing_bars=ticks_present_bar_missing,
        unexpected_extra_bars=unexpected_extra_bars
    )

