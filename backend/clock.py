"""
clock.py - "what day is it for THIS user?"

Streaks, daily tasks and check-ins all work on calendar days in the USER'S timezone
(users.timezone, default Asia/Kolkata). Timestamps in the database are naive UTC.

Tests freeze time by patching `clock.utcnow` (always call it as `clock.utcnow()`).
"""
from datetime import date, datetime, timedelta, timezone
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:                                    # pragma: no cover (python < 3.9)
    ZoneInfo = None

DEFAULT_TIMEZONE = "Asia/Kolkata"
_IST = timezone(timedelta(hours=5, minutes=30))        # last-resort fallback if tz data is missing


def utcnow() -> datetime:
    """Naive UTC 'now' (the same convention as every DateTime column in models.py)."""
    return datetime.utcnow()


def user_tz(user) -> timezone:
    """The user's tzinfo. Unknown / empty names fall back to the default, never raise."""
    for name in (getattr(user, "timezone", None), DEFAULT_TIMEZONE):
        if name and ZoneInfo is not None:
            try:
                return ZoneInfo(name)
            except Exception:
                continue
    return _IST


def to_local(user, utc_naive: datetime) -> datetime:
    """A naive-UTC datetime as an aware datetime in the user's timezone."""
    return utc_naive.replace(tzinfo=timezone.utc).astimezone(user_tz(user))


def local_now(user, now: Optional[datetime] = None) -> datetime:
    return to_local(user, now or utcnow())


def local_today(user, now: Optional[datetime] = None) -> date:
    return local_now(user, now).date()


def local_date(user, utc_naive: Optional[datetime]) -> Optional[date]:
    """Calendar day (user's timezone) of a stored UTC timestamp; None if there is none."""
    return to_local(user, utc_naive).date() if utc_naive else None
