"""
Part 6 endpoints: daily check-in, weekly review, notifications, settings and the cron hook.

Everything except /internal/cron/* needs a logged-in user (JWT). The cron endpoint is protected by
the CRON_SECRET header instead, and is switched off while CRON_SECRET is not set.
"""
import os
import secrets
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import emailer
import followups
import plans
from auth import get_current_user
from coach_router import RateLimiter
from models import Notification, User, get_db

router = APIRouter(tags=["followups"])
review_limiter = RateLimiter(5)       # a weekly review may call the LLM


# ── check-in ──────────────────────────────────────────────────────────────────
class CheckInRequest(BaseModel):
    mood: Optional[int] = Field(default=None, ge=1, le=5)
    note: Optional[str] = Field(default=None, max_length=followups.MAX_NOTE_CHARS)

    @model_validator(mode="after")
    def _something_given(self):
        if self.mood is None and not (self.note or "").strip():
            raise ValueError("send a mood (1-5) or a note")
        return self


@router.get("/coach/checkin/today")
def checkin_today(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """What the Coach should say right now, built from the student's real data (computed when asked)."""
    return followups.build_checkin(db, user)


@router.post("/coach/checkin")
def save_checkin(body: CheckInRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return followups.save_checkin(db, user, body.mood, body.note)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ── weekly review ─────────────────────────────────────────────────────────────
def _review_payload(db: Session, user: User, plan) -> dict:
    return {"review": plan.review, "plan": plans.plan_dict(db, user, plan)} if plan else {"review": None, "plan": None}


@router.get("/plan/weekly-review")
def get_weekly_review(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The proposed next week (if a review was started and not yet confirmed)."""
    return _review_payload(db, user, plans.get_proposed_plan(db, user.id))


@router.post("/plan/weekly-review")
def start_weekly_review(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Summarise the week and PROPOSE next week's plan. Nothing is replaced until /confirm."""
    wait = review_limiter.check(user.id)
    if wait is not None:
        raise HTTPException(status_code=429, detail=f"Too many requests. Please wait {wait}s and try again.",
                            headers={"Retry-After": str(wait)})
    try:
        proposed = followups.weekly_review(db, user)
    except followups.FollowupError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    return _review_payload(db, user, proposed)


@router.post("/plan/weekly-review/confirm")
def confirm_weekly_review(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        plan = followups.confirm_review(db, user)
    except followups.FollowupError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    return {"plan": plans.plan_dict(db, user, plan)}


@router.delete("/plan/weekly-review")
def discard_weekly_review(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"discarded": followups.discard_review(db, user)}


# ── notifications ─────────────────────────────────────────────────────────────
@router.get("/notifications")
def list_notifications(limit: int = Query(20, ge=1, le=50), db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    rows = (db.query(Notification).filter(Notification.user_id == user.id)
            .order_by(Notification.id.desc()).limit(limit).all())
    unread = db.query(Notification).filter(Notification.user_id == user.id, Notification.read.is_(False)).count()
    return {
        "unread": unread,
        "items": [{"id": n.id, "type": n.type, "message": n.message, "read": n.read,
                   "created_at": n.created_at.isoformat() + "Z" if n.created_at else None} for n in rows],
    }


@router.post("/notifications/read")
def mark_notifications_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = (db.query(Notification).filter(Notification.user_id == user.id, Notification.read.is_(False))
         .update({"read": True}))
    db.commit()
    return {"marked_read": n}


# ── settings ──────────────────────────────────────────────────────────────────
class SettingsIn(BaseModel):
    notify_email: bool


@router.get("/settings")
def get_settings(user: User = Depends(get_current_user)):
    return {"notify_email": bool(user.notify_email), "email_available": emailer.email_configured(),
            "email": user.email}


@router.put("/settings")
def update_settings(body: SettingsIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    user.notify_email = body.notify_email
    db.commit()
    return {"notify_email": bool(user.notify_email), "email_available": emailer.email_configured(),
            "email": user.email}


# ── cron (called by GitHub Actions, not by users) ─────────────────────────────
def require_cron_secret(x_cron_secret: Optional[str] = Header(default=None)) -> None:
    expected = os.getenv("CRON_SECRET")
    if not expected:
        raise HTTPException(status_code=503, detail="Cron endpoints are disabled: set CRON_SECRET on the server")
    if not x_cron_secret or not secrets.compare_digest(x_cron_secret.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Invalid cron secret")


@router.post("/internal/cron/daily-nudges", dependencies=[Depends(require_cron_secret)])
def daily_nudges(slot: Literal["morning", "evening"] = Query("morning"), db: Session = Depends(get_db)):
    """
    Creates in-app notifications for everyone with pending tasks (+ emails to users who opted in, when a
    provider is configured). Idempotent per user, slot and day. Works without any email setup.
    """
    try:
        return followups.run_daily_nudges(db, slot)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
