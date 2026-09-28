from datetime import UTC, datetime

from app.data.time_profile import (
    OffsetPeriod,
    TimeProfile,
    mt5_label_to_utc,
    utc_to_mt5_label,
)


def test_utc_to_mt5_label_current_utc3():
    # 2026-09-24 00:00:00 UTC
    dt = datetime(2026, 9, 24, 0, 0, tzinfo=UTC)
    # Expected server time is 03:00:00. Epoch for 2026-09-24 03:00:00 is 1790218800.
    # 1790208000 + 10800 = 1790218800
    res = utc_to_mt5_label(dt, 3.0)
    assert res == 1790218800

def test_mt5_label_to_utc_current_utc3():
    raw_ts = 1790218800
    dt = mt5_label_to_utc(raw_ts, 3.0)
    assert dt == datetime(2026, 9, 24, 0, 0, tzinfo=UTC)

def test_round_trip():
    dt = datetime(2026, 1, 1, 15, 30, tzinfo=UTC)
    raw = utc_to_mt5_label(dt, 2.5)
    dt_back = mt5_label_to_utc(raw, 2.5)
    assert dt == dt_back

def test_no_machine_local_dependency():
    # Using specific integer constants to ensure local tz doesn't interfere
    dt = datetime.fromtimestamp(1000000000, tz=UTC)
    # 1000000000 + 3600 = 1000003600
    assert utc_to_mt5_label(dt, 1.0) == 1000003600
    assert mt5_label_to_utc(1000003600, 1.0) == datetime.fromtimestamp(1000000000, tz=UTC)

def test_profile_utc2():
    prof = TimeProfile(
        profile_id="test_utc2",
        broker="test",
        server="test",
        symbol="EURUSD",
        source_time_basis="server",
        periods=[OffsetPeriod(effective_from=None, effective_to=None, offset_hours=2.0)]
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = datetime(2026, 1, 2, tzinfo=UTC)
    ranges = prof.get_subranges(start, end)
    assert len(ranges) == 1
    assert ranges[0][0] == start
    assert ranges[0][1] == end
    assert ranges[0][2] == 2.0

def test_profile_transition():
    # Transition at 2026-03-01 00:00:00 UTC (Epoch 1772323200)
    transition_epoch = datetime(2026, 3, 1, tzinfo=UTC).timestamp()
    prof = TimeProfile(
        profile_id="test_trans",
        broker="test",
        server="test",
        symbol="EURUSD",
        source_time_basis="server",
        periods=[
            OffsetPeriod(effective_from=None, effective_to=transition_epoch, offset_hours=2.0),
            OffsetPeriod(effective_from=transition_epoch, effective_to=None, offset_hours=3.0)
        ]
    )
    start = datetime(2026, 2, 28, tzinfo=UTC)
    end = datetime(2026, 3, 2, tzinfo=UTC)
    ranges = prof.get_subranges(start, end)
    assert len(ranges) == 2
    assert ranges[0][0] == start
    assert ranges[0][1] == datetime(2026, 3, 1, tzinfo=UTC)
    assert ranges[0][2] == 2.0
    
    assert ranges[1][0] == datetime(2026, 3, 1, tzinfo=UTC)
    assert ranges[1][1] == end
    assert ranges[1][2] == 3.0

def test_request_crossing_transition_splits_correctly():
    # Same as above, ensuring we handle arbitrary bounds
    transition_epoch = datetime(2026, 3, 1, tzinfo=UTC).timestamp()
    prof = TimeProfile(
        profile_id="test_trans",
        broker="test",
        server="test",
        symbol="EURUSD",
        source_time_basis="server",
        periods=[
            OffsetPeriod(effective_from=None, effective_to=transition_epoch, offset_hours=2.0),
            OffsetPeriod(effective_from=transition_epoch, effective_to=None, offset_hours=3.0)
        ]
    )
    
    # Request exactly across the boundary
    # A single day spanning 12 hours before and 12 hours after
    start = datetime(2026, 2, 28, 12, 0, tzinfo=UTC)
    end = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    ranges = prof.get_subranges(start, end)
    
    # Verify split logic
    assert len(ranges) == 2
    assert ranges[0] == (start, datetime(2026, 3, 1, tzinfo=UTC), 2.0)
    assert ranges[1] == (datetime(2026, 3, 1, tzinfo=UTC), end, 3.0)
