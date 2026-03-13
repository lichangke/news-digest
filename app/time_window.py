from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


def get_time_window(run_type: str, tz_name: str):
    tz = ZoneInfo(tz_name)
    now = datetime.now(tz)
    day = now.date()
    if run_type == "morning":
        prev_day = day - timedelta(days=1)
        return (
            datetime.combine(prev_day, time(17, 0), tzinfo=tz),
            datetime.combine(day, time(8, 0), tzinfo=tz),
        )
    if run_type == "evening":
        return (
            datetime.combine(day, time(8, 0), tzinfo=tz),
            datetime.combine(day, time(17, 0), tzinfo=tz),
        )
    raise ValueError(f"Unsupported run_type: {run_type}")
