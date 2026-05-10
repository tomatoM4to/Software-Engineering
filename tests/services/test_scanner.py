from app.services.scanner import get_prev_minute


def test_get_prev_minute():
    # Normal case: Same day
    assert get_prev_minute("20260510", "093000") == ("20260510", "092900")

    # Border case: 09:00 boundary (Monday 2026-05-11 -> Friday 2026-05-08)
    # 2026-05-11 is Monday. 09:00:00 - 1min -> should jump to Friday 15:30:00
    # Note: 2026-05-10 is Sunday, so 2026-05-11 is Monday.
    assert get_prev_minute("20260511", "090000") == ("20260508", "153000")

    # Border case: 09:00 boundary (Tuesday 2026-05-12 -> Monday 2026-05-11)
    assert get_prev_minute("20260512", "090000") == ("20260511", "153000")
