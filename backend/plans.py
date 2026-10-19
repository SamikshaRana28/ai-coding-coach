"""
plans.py - Part 5 service layer around the stored plan: read it, tick tasks, auto-complete
tasks when a problem is solved, reschedule missed ones.

The plan itself is built by agent/planner.py. Streak rules live in streaks.py.
"""
from datetime import date, datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

import clock
import streaks
from models import DailyTask, Problem, StudyPlan, User


# ── reading ───────────────────────────────────────────────────────────────────
def get_active_plan(db: Session, user_id: int) -> Optional[StudyPlan]:
    return (
        db.query(StudyPlan)
        .filter(StudyPlan.user_id == user_id, StudyPlan.status == "active")
        .order_by(StudyPlan.id.desc())
        .first()
    )


def get_proposed_plan(db: Session, user_id: int) -> Optional[StudyPlan]:
    return (
        db.query(StudyPlan)
        .filter(StudyPlan.user_id == user_id, StudyPlan.status == "proposed")
        .order_by(StudyPlan.id.desc())
        .first()
    )


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() + "Z" if dt else None          # stored as naive UTC


def task_dict(t: DailyTask, problems: Optional[dict] = None) -> dict:
    info = (problems or {}).get(t.problem_id)
    return {
        "id": t.id,
        "date": t.date.isoformat(),
        "kind": t.kind,
        "title": t.title,
        "problem_id": t.problem_id,
        "difficulty": info.difficulty if info else None,
        "status": t.status,
        "completed_at": _iso(t.completed_at),
    }


def _problem_lookup(db: Session, tasks: List[DailyTask]) -> dict:
    ids = {t.problem_id for t in tasks if t.problem_id}
    if not ids:
        return {}
    return {p.id: p for p in db.query(Problem).filter(Problem.id.in_(ids))}


def progress(tasks: List[DailyTask]) -> dict:
    done = sum(1 for t in tasks if t.status == "done")
    skipped = sum(1 for t in tasks if t.status == "skipped")
    total = len(tasks)
    return {
        "done": done, "skipped": skipped, "pending": total - done - skipped, "total": total,
        "percent": round(100 * done / total) if total else 0,
    }


def plan_tasks(db: Session, plan: StudyPlan) -> List[DailyTask]:
    return db.query(DailyTask).filter(DailyTask.plan_id == plan.id).order_by(DailyTask.date, DailyTask.id).all()


def plan_dict(db: Session, user, plan: StudyPlan) -> dict:
    today = clock.local_today(user)
    tasks = plan_tasks(db, plan)
    problems = _problem_lookup(db, tasks)
    by_date: dict = {}
    for t in tasks:
        by_date.setdefault(t.date, []).append(t)
    start = plan.week_start
    days = []
    for i in range(7):
        d = start + timedelta(days=i)
        days.append({
            "date": d.isoformat(),
            "weekday": d.strftime("%a"),
            "is_today": d == today,
            "is_past": d < today,
            "tasks": [task_dict(t, problems) for t in by_date.get(d, [])],
        })
    return {
        "id": plan.id,
        "status": plan.status,
        "week_start": start.isoformat(),
        "week_end": (start + timedelta(days=6)).isoformat(),
        "summary": plan.summary,
        "focus_topics": plan.focus_topics or [],
        "goal": plan.goal,
        "minutes_per_day": plan.minutes_per_day,
        "source": plan.source,
        "review": plan.review,
        "expired": today > start + timedelta(days=6),
        "days": days,
        "progress": progress(tasks),
    }


def today_tasks(db: Session, user, now: Optional[datetime] = None) -> dict:
    """Tasks dated today (local) in the active plan."""
    today = clock.local_today(user, now)
    plan = get_active_plan(db, user.id)
    tasks = []
    if plan is not None:
        tasks = (
            db.query(DailyTask)
            .filter(DailyTask.plan_id == plan.id, DailyTask.date == today)
            .order_by(DailyTask.id).all()
        )
    problems = _problem_lookup(db, tasks)
    return {
        "date": today.isoformat(),
        "has_plan": plan is not None,
        "tasks": [task_dict(t, problems) for t in tasks],
        "progress": progress(tasks),
    }


# ── changing tasks ────────────────────────────────────────────────────────────
def get_task(db: Session, user_id: int, task_id: int) -> Optional[DailyTask]:
    """The user's own task, or None (another user's task id looks exactly like a missing one)."""
    return db.query(DailyTask).filter(DailyTask.id == task_id, DailyTask.user_id == user_id).first()


def complete_task(db: Session, user, task: DailyTask, now: Optional[datetime] = None) -> bool:
    """Mark done + count the day for the streak. Returns False if it was already done (nothing changes).
    Does NOT commit."""
    if task.status == "done":
        return False
    task.status = "done"
    task.completed_at = now or clock.utcnow()
    streaks.record_activity(db, user, task.completed_at)
    return True


def skip_task(task: DailyTask) -> bool:
    """pending -> skipped. A done task stays done. Returns whether anything changed."""
    if task.status != "pending":
        return False
    task.status = "skipped"
    return True


def reschedule_missed(db: Session, user, now: Optional[datetime] = None) -> int:
    """Move every pending task dated before today (active plan) to today. Returns how many moved."""
    today = clock.local_today(user, now)
    plan = get_active_plan(db, user.id)
    if plan is None:
        return 0
    rows = (
        db.query(DailyTask)
        .filter(DailyTask.plan_id == plan.id, DailyTask.status == "pending", DailyTask.date < today)
        .all()
    )
    for t in rows:
        t.date = today
    return len(rows)


def on_problem_activity(db: Session, user_id: int, problem_id: int, *, clean: bool, newly_solved: bool,
                        now: Optional[datetime] = None) -> int:
    """
    Called by /problems/{id}/submit and /mark-solved BEFORE their commit, so everything lands in
    one transaction.
      * a clean review completes the pending plan tasks that point at this problem
      * a problem solved for the first time counts the day for the streak, task or no task
    Returns the number of tasks completed.
    """
    user = db.get(User, user_id)
    if user is None:
        return 0
    completed = 0
    if clean:
        plan = get_active_plan(db, user_id)
        if plan is not None:
            for t in (
                db.query(DailyTask)
                .filter(DailyTask.plan_id == plan.id, DailyTask.problem_id == problem_id,
                        DailyTask.status.in_(["pending", "skipped"]))
            ):
                completed += complete_task(db, user, t, now)
    if newly_solved:
        streaks.record_activity(db, user, now)
    return completed
