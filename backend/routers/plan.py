"""
Part 5 endpoints: study plan, daily tasks, streak.

The user always comes from the JWT (get_current_user). Task ids belong to one user: someone
else's task id answers 404, exactly like a missing one.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import plans
import streaks
from agent import planner
from auth import get_current_user
from coach_router import RateLimiter
from models import User, get_db

router = APIRouter(tags=["plan"])

# plan generation may call the LLM: a few per minute per user is plenty
plan_limiter = RateLimiter(5)


class PlanRequest(BaseModel):
    goal: Optional[str] = Field(default=None, max_length=planner.MAX_GOAL_CHARS)      # "interview in 4 weeks"
    minutes_per_day: Optional[int] = Field(default=None, ge=10, le=480)
    focus_topic: Optional[str] = Field(default=None, max_length=30)                    # "make me a plan for graphs"


def _generate(db: Session, user: User, body: PlanRequest):
    wait = plan_limiter.check(user.id)
    if wait is not None:
        raise HTTPException(status_code=429, detail=f"Too many plan requests. Please wait {wait}s and try again.",
                            headers={"Retry-After": str(wait)})
    try:
        return planner.create_plan(db, user, goal=body.goal, minutes_per_day=body.minutes_per_day,
                                   focus_topic=body.focus_topic)
    except planner.PlanError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plan/generate")
def generate_plan(body: Optional[PlanRequest] = None, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    """Build a new 7-day plan from the student's real data. The previous plan is archived."""
    plan = _generate(db, user, body or PlanRequest())
    return plans.plan_dict(db, user, plan)


@router.get("/plan/current")
def current_plan(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    plan = plans.get_active_plan(db, user.id)
    return {"plan": plans.plan_dict(db, user, plan) if plan else None}


@router.get("/plan/focus")
def where_to_focus(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Weak topics + patterns to study, with honest wording when there is little data (Dashboard section)."""
    w = planner.analyze_weaknesses(db, user.id)
    return {k: w[k] for k in ("focus", "patterns", "low_data", "total_attempts", "source", "note")}


@router.get("/tasks/today")
def tasks_today(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return plans.today_tasks(db, user)


def _own_task(db: Session, user: User, task_id: int):
    task = plans.get_task(db, user.id, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Idempotent: completing a done task changes nothing and cannot count the day twice."""
    task = _own_task(db, user, task_id)
    try:
        changed = plans.complete_task(db, user, task)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return {"task": plans.task_dict(task), "changed": changed, "streak": streaks.streak_summary(db, user)}


@router.post("/tasks/{task_id}/skip")
def skip_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = _own_task(db, user, task_id)
    if task.status == "done":
        raise HTTPException(status_code=409, detail="This task is already completed")
    plans.skip_task(task)
    db.commit()
    return {"task": plans.task_dict(task)}


@router.post("/tasks/reschedule")
def reschedule_tasks(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Move the unfinished tasks of earlier days to today."""
    moved = plans.reschedule_missed(db, user)
    db.commit()
    return {"moved": moved, "today": plans.today_tasks(db, user)}


@router.get("/streak")
def get_streak(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return streaks.streak_summary(db, user)
