from datetime import UTC, datetime

from pydantic import BaseModel


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
        for p in self.periods:
            p_start = p.effective_from if p.effective_from is not None else -float('inf')
            p_end = p.effective_to if p.effective_to is not None else float('inf')
            
            utc_epoch = float(raw_timestamp) - (p.offset_hours * 3600.0)
            if p_start <= utc_epoch < p_end:
                return datetime.fromtimestamp(utc_epoch, tz=UTC)
                
        raise ValueError(f"No valid time profile period found for raw timestamp {raw_timestamp}")
        
    def add_canonical_column(self, df, raw_col='time', new_col='timestamp'):
        import pandas as pd
        if df.empty:
            df[new_col] = pd.Series(dtype='datetime64[ns, UTC]')
            return df
        
        def _convert(x):
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
