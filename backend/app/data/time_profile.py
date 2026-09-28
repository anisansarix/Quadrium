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

            # If the period is entirely before our current start, skip
            if p_end <= current_start:
                continue
                
            # If the period covers our current start
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


def utc_to_mt5_label(dt_utc: datetime, offset_hours: float) -> int:
    """
    Convert a canonical UTC datetime into an MT5 raw integer epoch (Server Time).
    We do this by adding the offset to the UTC epoch.
    """
    epoch = dt_utc.timestamp()
    shifted_epoch = epoch + (offset_hours * 3600.0)
    return int(shifted_epoch)


def mt5_label_to_utc(raw_timestamp: int, offset_hours: float) -> datetime:
    """
    Convert a raw MT5 Server Time epoch back into a canonical UTC datetime.
    We do this by subtracting the offset from the Server Time epoch.
    """
    true_epoch = float(raw_timestamp) - (offset_hours * 3600.0)
    return datetime.fromtimestamp(true_epoch, tz=UTC)

def get_metaquotes_demo_phase1_profile() -> TimeProfile:
    # A hardcoded UTC+3 profile for Phase 1
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
