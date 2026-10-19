"""
streaks.py - Part 5 streak rules.

A calendar day counts when the student completed at least one daily task OR solved at least one
problem on that day, in THE USER'S timezone (users.timezone).

  * same day again            -> nothing changes (idempotent: two tasks on one day count once)
  * the day after the last    -> current_streak + 1
  * a gap of 1+ missed days   -> the streak starts again at 1 on the next active day
  * reading a streak whose last active day is older than yesterday shows 0 (the streak is broken),
    even before the next activity writes anything.
  * longest_streak only ever goes up.
"""
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import clock
from models import DailyTask, UserProblem, UserStreak


def _get_or_create(db: Session, user_id: int) -> UserStreak:
    row = db.get(UserStreak, user_id)
    if row is not None:
        return row
    row = UserStreak(user_id=user_id, current_streak=0, longest_streak=0, last_active_date=None)
    try:
        with db.begin_nested():            # savepoint: a duplicate only rolls back this insert
            db.add(row)
    except IntegrityError:
        row = db.get(UserStreak, user_id)
    return row


def record_activity(db: Session, user, when: Optional[datetime] = None) -> UserStreak:
    """Count the day of `when` (default: now) as active. Does NOT commit: the caller does."""
    day = clock.local_date(user, when or clock.utcnow())
    s = _get_or_create(db, user.id)
    last = s.last_active_date

    if last is not None and day <= last:
        return s                            # same day (or an older timestamp): already counted
    if last is not None and day == last + timedelta(days=1):
        s.current_streak = (s.current_streak or 0) + 1
    else:
        s.current_streak = 1                # first ever activity, or the streak was broken
    s.longest_streak = max(s.longest_streak or 0, s.current_streak)
    s.last_active_date = day
    return s


def effective_current(s: Optional[UserStreak], today: date) -> int:
    """The streak as the student should see it today (0 once a whole day was missed)."""
    if s is None or s.last_active_date is None:
        return 0
    if s.last_active_date >= today - timedelta(days=1):
        return s.current_streak or 0
    return 0


def streak_summary(db: Session, user, now: Optional[datetime] = None) -> dict:
    today = clock.local_today(user, now)
    s = db.get(UserStreak, user.id)
    current = effective_current(s, today)
    return {
        "current_streak": current,
        "longest_streak": max((s.longest_streak if s else 0) or 0, current),
        "last_active_date": s.last_active_date.isoformat() if s and s.last_active_date else None,
        "active_today": bool(s and s.last_active_date == today),
        "today": today.isoformat(),
        "week": week_activity(db, user, now),
    }


def active_days(db: Session, user, start: date, end: date) -> set:
    """Local calendar days in [start, end] with a completed task or a solved problem (read from the data)."""
    # a generous UTC window around the local range, then filter by the converted local date
    lo = datetime.combine(start - timedelta(days=1), datetime.min.time())
    hi = datetime.combine(end + timedelta(days=2), datetime.min.time())
    days = set()
    for (stamp,) in (
        db.query(DailyTask.completed_at)
        .filter(DailyTask.user_id == user.id, DailyTask.status == "done",
                DailyTask.completed_at >= lo, DailyTask.completed_at < hi)
    ):
        days.add(clock.local_date(user, stamp))
    for (stamp,) in (
        db.query(UserProblem.solved_at)
        .filter(UserProblem.user_id == user.id, UserProblem.solved_at >= lo, UserProblem.solved_at < hi)
    ):
        days.add(clock.local_date(user, stamp))
    return {d for d in days if d and start <= d <= end}


def week_activity(db: Session, user, now: Optional[datetime] = None) -> List[dict]:
    """The last 7 local days, oldest first: [{date, weekday, active}] for the 7-dot row."""
    today = clock.local_today(user, now)
    start = today - timedelta(days=6)
    active = active_days(db, user, start, today)
    out = []
    for i in range(7):
        d = start + timedelta(days=i)
        out.append({"date": d.isoformat(), "weekday": d.strftime("%a"), "active": d in active})
    return out
