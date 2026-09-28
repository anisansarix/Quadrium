from datetime import UTC, datetime, time

from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow


def test_calibrated_eurusd_phase1_calendar():
    # Sunday 21:00 UTC -> Friday 21:00 UTC
    config = ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=6, start_time=time(21, 0), end_day=4, end_time=time(21, 0))]
    )
    calendar = ConfigurableCalendar(config)
    
    # Excludes Sunday 20:59
    assert not len(calendar.get_expected_bars(datetime(2026, 9, 27, 20, 59, tzinfo=UTC), datetime(2026, 9, 27, 21, 0, tzinfo=UTC), "1min")) > 0
    
    # Includes Sunday 21:00
    assert len(calendar.get_expected_bars(datetime(2026, 9, 27, 21, 0, tzinfo=UTC), datetime(2026, 9, 27, 21, 1, tzinfo=UTC), "1min")) > 0
    
    # Includes Friday 20:59
    assert len(calendar.get_expected_bars(datetime(2026, 9, 25, 20, 59, tzinfo=UTC), datetime(2026, 9, 25, 21, 0, tzinfo=UTC), "1min")) > 0
    
    # Excludes Friday 21:00
    assert not len(calendar.get_expected_bars(datetime(2026, 9, 25, 21, 0, tzinfo=UTC), datetime(2026, 9, 25, 21, 1, tzinfo=UTC), "1min")) > 0
    
    # Produces exactly 7200 expected M1 timestamps over a complete week
    # Request from Sunday 00:00 to next Sunday 00:00
    start = datetime(2026, 9, 20, 0, 0, tzinfo=UTC)
    end = datetime(2026, 9, 27, 0, 0, tzinfo=UTC)
    expected_ts = calendar.get_expected_bars(start, end, "1min")
    assert len(expected_ts) == 7200
