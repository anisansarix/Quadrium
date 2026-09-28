from datetime import UTC, datetime

import pytest
from app.data.time_profile import (
    OffsetPeriod,
    TimeProfile,
)


def test_overlapping_period_failure():
    with pytest.raises(ValueError, match="Periods overlap"):
        TimeProfile(
            profile_id="test",
            broker="test",
            server="test",
            symbol="test",
            source_time_basis="test",
            periods=[
                OffsetPeriod(effective_from=None, effective_to=1000, offset_hours=3.0),
                OffsetPeriod(effective_from=999, effective_to=None, offset_hours=2.0)
            ]
        )

def test_gap_period_failure():
    with pytest.raises(ValueError, match="Periods have a gap"):
        TimeProfile(
            profile_id="test",
            broker="test",
            server="test",
            symbol="test",
            source_time_basis="test",
            periods=[
                OffsetPeriod(effective_from=None, effective_to=1000, offset_hours=3.0),
                OffsetPeriod(effective_from=1001, effective_to=None, offset_hours=2.0)
            ]
        )

def test_invalid_period_bounds():
    with pytest.raises(ValueError, match="must be less than"):
        TimeProfile(
            profile_id="test",
            broker="test",
            server="test",
            symbol="test",
            source_time_basis="test",
            periods=[
                OffsetPeriod(effective_from=1000, effective_to=1000, offset_hours=3.0)
            ]
        )

def test_utc3_to_utc2_transition():
    # A transition from UTC+3 to UTC+2
    # Let's say at UTC epoch 3600 (1970-01-01 01:00:00 UTC)
    tp = TimeProfile(
        profile_id="test",
        broker="test",
        server="test",
        symbol="test",
        source_time_basis="test",
        periods=[
            OffsetPeriod(effective_from=None, effective_to=3600, offset_hours=3.0),
            OffsetPeriod(effective_from=3600, effective_to=None, offset_hours=2.0)
        ]
    )
    
    # request crossing transition
    start_utc = datetime(1970, 1, 1, 0, 30, tzinfo=UTC)
    end_utc = datetime(1970, 1, 1, 1, 30, tzinfo=UTC)
    ranges = tp.get_subranges(start_utc, end_utc)
    
    assert len(ranges) == 2
    assert ranges[0][2] == 3.0
    assert ranges[0][1] == datetime(1970, 1, 1, 1, 0, tzinfo=UTC)
    assert ranges[1][2] == 2.0
    
    # uncovered interval failure
    # If the profile doesn't cover - this is already covered by the gap failure above which rejects the model itself.
    # What if the profile is finite but we request outside?
    tp2 = TimeProfile(
        profile_id="test",
        broker="test",
        server="test",
        symbol="test",
        source_time_basis="test",
        periods=[
            OffsetPeriod(effective_from=0, effective_to=3600, offset_hours=3.0)
        ]
    )
    with pytest.raises(ValueError, match="cannot cover"):
        tp2.get_subranges(datetime(1969, 12, 31, 0, 0, tzinfo=UTC), datetime(1970, 1, 1, 1, 0, tzinfo=UTC))
        
    # ambiguous raw timestamp failure
    # At transition 3600, UTC+3 ended. The last raw time was 3600 + 3*3600 = 14400.
    # The new period is UTC+2. The first raw time is 3600 + 2*3600 = 10800.
    # So raw times between 10800 and 14400 are ambiguous!
    # Let's test 11000.
    with pytest.raises(ValueError, match="Ambiguous raw timestamp"):
        tp.convert_raw_to_utc(11000)
        
    # raw timestamp exactly at transition
    # The new period starts at UTC 3600. Raw time is 10800. 
    # Is 10800 ambiguous?
    # At UTC 3600, period 2 has raw 10800.
    # But for period 1, UTC 00:00 (0) has raw 10800!
    # So 10800 is ambiguous!
    with pytest.raises(ValueError, match="Ambiguous raw timestamp"):
        tp.convert_raw_to_utc(10800)
        
    # UTC 100 has raw 10800 + 100 = 10900. Ambiguous!
    
    # Raw 14400 (last raw of period 1)
    # Maps to UTC 3600 under period 1, but period 1 is [..., 3600) so it's NOT in period 1!
    # Under period 2, it maps to UTC 7200. Period 2 is [3600, ...). So it's valid under period 2!
    res = tp.convert_raw_to_utc(14400)
    assert res == datetime(1970, 1, 1, 2, 0, tzinfo=UTC)
