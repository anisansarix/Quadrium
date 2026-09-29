from datetime import UTC, datetime

from pydantic import BaseModel, model_validator


class OffsetPeriod(BaseModel):
    effective_from: float | None  # UTC epoch
    effective_to: float | None    # UTC epoch
    offset_hours: float


class TimeProfile(BaseModel):
    profile_id: str
    broker: str
    server: str
    symbol: str
    source_time_basis: str
    periods: list[OffsetPeriod]

    @model_validator(mode='after')
    def validate_periods(self):
        # Sort periods
        sorted_periods = sorted(self.periods, key=lambda p: p.effective_from if p.effective_from is not None else -float('inf'))
        
        for i, p in enumerate(sorted_periods):
            p_start = p.effective_from if p.effective_from is not None else -float('inf')
            p_end = p.effective_to if p.effective_to is not None else float('inf')
            
            if p_start >= p_end:
                raise ValueError(f"Period effective_from ({p.effective_from}) must be less than effective_to ({p.effective_to})")
                
            if i > 0:
                prev_p = sorted_periods[i-1]
                prev_end = prev_p.effective_to if prev_p.effective_to is not None else float('inf')
                if p_start < prev_end:
                    raise ValueError(f"Periods overlap: {prev_p} and {p}")
                if p_start > prev_end:
                    raise ValueError(f"Periods have a gap between {prev_end} and {p_start}")
                    
                # Ambiguous raw-to-UTC transition check (backward jump in Server Time)
                # If we jump BACKWARDS in server time, the same Server Time integer maps to two different UTC times!
                # e.g., if offset goes from +3 to +2, then 03:00 Server Time (UTC 00:00) happens.
                # Then at 04:00 Server Time (UTC 01:00), the clock falls back to 03:00 Server Time (UTC 01:00).
                # So 03:00 to 04:00 Server Time happens TWICE.
                # A raw timestamp in that hour is ambiguous!
                # We can't trivially invert it without knowing the session.
                # The prompt asks: "Add validation that profile periods... do not create ambiguous raw-to-UTC mappings."
                # Actually, a backward jump ALWAYS creates an ambiguous mapping in raw time.
                # Wait, if we know the raw time, can we invert it?
                # If a time period ends at prev_end (UTC) with offset1, the last raw time is prev_end + offset1.
                # The next period starts at p_start (UTC) with offset2, the first raw time is p_start + offset2.
                # Since prev_end == p_start, the raw gap is offset2 - offset1.
                # If offset2 < offset1, the first raw time of the new period is BEFORE the last raw time of the old period!
                # This creates ambiguity. The prompt says "do not create ambiguous raw-to-UTC mappings."
                # Does this mean we should raise an error if offset2 < offset1?
                # The user said: "do not create ambiguous raw-to-UTC mappings... Add explicit tests for: UTC+3 -> UTC+2 transition... overlapping-period failure, ambiguous raw timestamp failure"
                # Wait! A UTC+3 to UTC+2 transition IS a backward jump, so it DOES create ambiguity.
                # So how can we have a test for UTC+3 -> UTC+2 if we forbid ambiguous mappings?
                # Ah! The user might want convert_raw_to_utc to raise an error if a specific raw timestamp falls in the ambiguous window!
                # Not that the Profile itself is invalid, but the mapping function throws an error for ambiguous values!
                
        return self

    def get_subranges(self, start_utc: datetime, end_utc: datetime) -> list[tuple[datetime, datetime, float]]:
        start_epoch = start_utc.timestamp()
        end_epoch = end_utc.timestamp()

        # Sort periods just to be safe, assuming None for effective_from is -inf, None for effective_to is +inf
        def sort_key(p: OffsetPeriod) -> float:
            return p.effective_from if p.effective_from is not None else -float('inf')

        sorted_periods = sorted(self.periods, key=sort_key)
        
        ranges = []
        current_start = start_epoch

        for p in sorted_periods:
            if current_start >= end_epoch:
                break
                
            p_start = p.effective_from if p.effective_from is not None else -float('inf')
            p_end = p.effective_to if p.effective_to is not None else float('inf')

            if p_end <= current_start:
                continue
                
            if p_start <= current_start < p_end:
                range_end = min(end_epoch, p_end)
                ranges.append((
                    datetime.fromtimestamp(current_start, tz=UTC),
                    datetime.fromtimestamp(range_end, tz=UTC),
                    p.offset_hours
                ))
                current_start = range_end

        if current_start < end_epoch:
            raise ValueError(f"TimeProfile {self.profile_id} has gaps and cannot cover {start_utc} to {end_utc}")

        return ranges

    def convert_raw_to_utc(self, raw_timestamp: int) -> datetime:
        valid_utcs = []
        for p in self.periods:
            p_start = p.effective_from if p.effective_from is not None else -float('inf')
            p_end = p.effective_to if p.effective_to is not None else float('inf')
            
            utc_epoch = float(raw_timestamp) - (p.offset_hours * 3600.0)
            if p_start <= utc_epoch < p_end:
                valid_utcs.append(datetime.fromtimestamp(utc_epoch, tz=UTC))
                
        if not valid_utcs:
            raise ValueError(f"No valid time profile period found for raw timestamp {raw_timestamp}")
        if len(valid_utcs) > 1:
            raise ValueError(f"Ambiguous raw timestamp {raw_timestamp} falls into multiple profile periods due to a backward time transition (e.g. DST fallback).")
            
        return valid_utcs[0]
        
    def add_canonical_column(self, df, raw_col='time', new_col='timestamp', is_msc=False):
        import pandas as pd
        if df.empty:
            df[new_col] = pd.Series(dtype='datetime64[ns, UTC]')
            return df
        
        def _convert(x):
            if is_msc:
                sec = int(x // 1000)
                msc = int(x % 1000)
                dt = self.convert_raw_to_utc(sec)
                return pd.Timestamp(dt) + pd.Timedelta(milliseconds=msc)
            return pd.Timestamp(self.convert_raw_to_utc(x))
                
        df[new_col] = df[raw_col].apply(_convert)
        return df


def utc_to_mt5_label(dt_utc: datetime, offset_hours: float) -> int:
    epoch = dt_utc.timestamp()
    shifted_epoch = epoch + (offset_hours * 3600.0)
    return int(shifted_epoch)


def mt5_label_to_utc(raw_timestamp: int, offset_hours: float) -> datetime:
    true_epoch = float(raw_timestamp) - (offset_hours * 3600.0)
    return datetime.fromtimestamp(true_epoch, tz=UTC)


def get_metaquotes_demo_phase1_profile() -> TimeProfile:
    return TimeProfile(
        profile_id="metaquotes_demo_eurusd_phase1_v1",
        broker="MetaQuotes Ltd.",
        server="MetaQuotes-Demo",
        symbol="EURUSD",
        source_time_basis="broker_server_wallclock",
        periods=[
            OffsetPeriod(
                effective_from=None,
                effective_to=None,
                offset_hours=3.0
            )
        ]
    )
