"""
followups.py - Part 6: the Coach checks in on the student.

  * build_checkin()    in-app greeting / follow-ups, computed LAZILY when the app opens (always works,
                       even if the free host was asleep). Built only from real data.
  * save_checkin()     the student's "how was your day" answer.
  * weekly_review()    numbers for the finished week + a PROPOSED next plan (confirm_review() applies it).
  * run_daily_nudges() what the external cron calls: in-app notifications (+ optional email).
"""
import logging
from datetime import date, datetime, timedelta
from typing import Callable, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import clock
import emailer
import plans
import streaks
from models import CheckIn, DailyTask, HintEvent, Notification, Problem, StudyPlan, User, UserProblem
from problem_utils import primary_topic

log = logging.getLogger(__name__)

MORNING_BEFORE_HOUR = 12
EVENING_FROM_HOUR = 20
CHECKIN_FROM_HOUR = 18
MAX_NOTE_CHARS = 500
QUESTIONS = ["How was your day?", "Did you follow the schedule?"]
LIGHTER_WORDS = ("sick", "ill ", "fever", "overwhelm", "overload", "too much", "burnt", "burned", "exhaust",
                 "stress", "no time", "tired", "busy", "swamped", "can't cope", "cant cope")


class FollowupError(Exception):
    status_code = 409


class NothingToReview(FollowupError):
    status_code = 409


def _days(n: int) -> str:
    return f"{n} day{'' if n == 1 else 's'}"


def _tasks(n: int) -> str:
    return f"{n} task{'' if n == 1 else 's'}"


def part_of_day(hour: int) -> str:
    if hour < MORNING_BEFORE_HOUR:
        return "morning"
    return "evening" if hour >= EVENING_FROM_HOUR else "day"


# ── check-in (lazy, in-app) ───────────────────────────────────────────────────
def _checkin_dict(c: Optional[CheckIn]) -> Optional[dict]:
    if c is None:
        return None
    return {"date": c.date.isoformat(), "mood": c.mood, "note": c.note,
            "tasks_done": c.tasks_done, "tasks_total": c.tasks_total}


def _unread(db: Session, user_id: int) -> int:
    return db.query(Notification).filter(Notification.user_id == user_id, Notification.read.is_(False)).count()


def build_checkin(db: Session, user: User, now: Optional[datetime] = None) -> dict:
    local = clock.local_now(user, now)
    today, hour = local.date(), local.hour
    when = part_of_day(hour)
    name = (user.first_name or (user.name or "").split(" ")[0] or "there").strip()

    plan = plans.get_active_plan(db, user.id)
    proposed = plans.get_proposed_plan(db, user.id)
    info = plans.today_tasks(db, user, now)
    pending = [t for t in info["tasks"] if t["status"] == "pending"]
    done_n, total_n = info["progress"]["done"], info["progress"]["total"]
    streak = streaks.streak_summary(db, user, now)
    current = streak["current_streak"]

    messages: List[dict] = []
    expired = plan is not None and today > plan.week_start + timedelta(days=6)

    if proposed is not None:
        messages.append({"kind": "weekly_review", "text": "Your weekly review and next week's plan are ready. "
                         "Have a look and confirm when you like it.",
                         "actions": [{"id": "weekly_review", "label": "See my weekly review"}]})
    elif expired:
        messages.append({"kind": "weekly_review", "text": "Your plan week is over. Want to see how it went and get "
                         "next week's schedule?", "actions": [{"id": "weekly_review", "label": "Start my weekly review"}]})

    if plan is not None and not expired:
        overdue = (db.query(DailyTask)
                   .filter(DailyTask.plan_id == plan.id, DailyTask.status == "pending", DailyTask.date < today)
                   .all())
        if overdue:
            y = today - timedelta(days=1)
            y_rows = db.query(DailyTask).filter(DailyTask.plan_id == plan.id, DailyTask.date == y).all()
            y_missed = [t for t in y_rows if t.status == "pending"]
            if y_missed:
                y_done = sum(1 for t in y_rows if t.status == "done")
                text = f"You missed yesterday's tasks ({y_done}/{len(y_rows)} done)."
            else:
                text = f"You have {_tasks(len(overdue))} left over from earlier days."
            messages.append({"kind": "missed_yesterday", "text": text + " Want me to move them to today or lighten the plan?",
                             "actions": [{"id": "reschedule", "label": "Move them to today"},
                                         {"id": "lighten", "label": "Lighten my plan"}]})

        titles = "; ".join(t["title"] for t in pending[:4])
        if when == "morning":
            if total_n == 0:
                text = f"Good morning, {name}! Nothing is scheduled for today."
            else:
                text = f"Good morning, {name}! Today's tasks: {titles}."
            text += (f" Your streak is {_days(current)}." if current else " Finish one task today to start a streak.")
            messages.append({"kind": "morning", "text": text, "actions": []})
        elif when == "evening" and pending:
            text = f"You still have {_tasks(len(pending))} pending today."
            text += (" Your streak is already safe for today." if streak["active_today"]
                     else " Even one keeps your streak alive.")
            messages.append({"kind": "evening_pending", "text": text, "actions": []})
        elif total_n and not pending:
            messages.append({"kind": "all_done", "text": f"All {_tasks(total_n)} done today, great work! "
                             f"Streak: {_days(current)}.", "actions": []})
        elif total_n:
            messages.append({"kind": "welcome_back", "text": f"Welcome back, {name}! {done_n} of {total_n} tasks done today. "
                             f"Streak: {_days(current)}.", "actions": []})
    elif plan is None and proposed is None:
        messages.append({"kind": "no_plan", "text": f"Hi {name}! You don't have a study plan yet. Want me to build a "
                         "7-day plan from your progress?", "actions": [{"id": "generate_plan", "label": "Make my plan"}]})

    existing = db.query(CheckIn).filter(CheckIn.user_id == user.id, CheckIn.date == today).first()
    ask_checkin = existing is None and hour >= CHECKIN_FROM_HOUR
    unread = _unread(db, user.id)
    attention_kinds = {"weekly_review", "missed_yesterday", "evening_pending", "no_plan"}
    return {
        "date": today.isoformat(),
        "part_of_day": when,
        "messages": messages,
        "tasks_today": info,
        "streak": {k: streak[k] for k in ("current_streak", "longest_streak", "active_today")},
        "ask_checkin": ask_checkin,
        "questions": QUESTIONS if ask_checkin else [],
        "checkin_today": _checkin_dict(existing),
        "unread_notifications": unread,
        "needs_attention": bool(unread or ask_checkin or any(m["kind"] in attention_kinds for m in messages)),
    }


def wants_lighter_plan(mood: Optional[int], note: Optional[str]) -> bool:
    text = f" {(note or '').lower()} "
    return (mood is not None and mood <= 2) or any(w in text for w in LIGHTER_WORDS)


def save_checkin(db: Session, user: User, mood: Optional[int], note: Optional[str],
                 now: Optional[datetime] = None) -> dict:
    """Store today's check-in (one per day; a second save replaces it). Commits."""
    note = (note or "").strip()[:MAX_NOTE_CHARS] or None
    today = clock.local_today(user, now)
    info = plans.today_tasks(db, user, now)
    done_n, total_n = info["progress"]["done"], info["progress"]["total"]

    row = db.query(CheckIn).filter(CheckIn.user_id == user.id, CheckIn.date == today).first()
    if row is None:
        row = CheckIn(user_id=user.id, date=today)
        db.add(row)
    row.mood, row.note, row.tasks_done, row.tasks_total = mood, note, done_n, total_n
    try:
        db.commit()
    except IntegrityError:                      # two saves at once: keep the first, update it
        db.rollback()
        row = db.query(CheckIn).filter(CheckIn.user_id == user.id, CheckIn.date == today).one()
        row.mood, row.note, row.tasks_done, row.tasks_total = mood, note, done_n, total_n
        db.commit()

    lighter = wants_lighter_plan(mood, note)
    if lighter:
        reply = ("Thanks for telling me. That sounds like a heavy day, and that's okay. Want me to switch to a lighter "
                 "plan (2 short tasks a day) so you can keep going without burning out?")
        actions = [{"id": "lighten", "label": "Yes, lighten my plan"}]
    elif total_n and done_n < total_n:
        reply = f"Thanks for checking in! {done_n}/{total_n} tasks done today. Even one small task keeps your streak alive."
        actions = []
    else:
        reply = "Thanks for checking in! Keep it up."
        actions = []
    return {"checkin": _checkin_dict(row), "reply": reply, "suggest_lighter": lighter, "actions": actions}


def checkin_context(db: Session, user: User) -> Optional[str]:
    """One line for the Coach chat prompt (DATA, written by the student), so it can offer a lighter plan."""
    today = clock.local_today(user)
    c = db.query(CheckIn).filter(CheckIn.user_id == user.id, CheckIn.date == today).first()
    if c is None or (c.mood is None and not c.note):
        return None
    parts = [f"Today's check-in: mood {c.mood}/5" if c.mood else "Today's check-in"]
    if c.note:
        parts.append(f"note: {c.note}")
    parts.append(f"tasks done {c.tasks_done}/{c.tasks_total}")
    if wants_lighter_plan(c.mood, c.note):
        parts.append("the student may be overloaded or unwell: offer a lighter plan (create_study_plan with fewer minutes_per_day)")
    return "; ".join(parts)


# ── weekly review ─────────────────────────────────────────────────────────────
def _local_range(user: User, start: date, end: date):
    """naive-UTC bounds that surely cover the local days [start, end]; callers filter by local date."""
    return (datetime.combine(start - timedelta(days=1), datetime.min.time()),
            datetime.combine(end + timedelta(days=2), datetime.min.time()))


def review_stats(db: Session, user: User, plan: StudyPlan, now: Optional[datetime] = None) -> dict:
    today = clock.local_today(user, now)
    start = plan.week_start
    end = min(today, start + timedelta(days=6))
    lo, hi = _local_range(user, start, end)

    tasks = plans.plan_tasks(db, plan)
    prog = plans.progress(tasks)

    solved_by_topic: dict = {}
    rows = (db.query(UserProblem, Problem).join(Problem, Problem.id == UserProblem.problem_id)
            .filter(UserProblem.user_id == user.id, UserProblem.solved_at >= lo, UserProblem.solved_at < hi))
    solved_total = 0
    for up, p in rows:
        d = clock.local_date(user, up.solved_at)
        if d and start <= d <= end:
            solved_total += 1
            t = primary_topic(p.topics)
            solved_by_topic[t] = solved_by_topic.get(t, 0) + 1

    hints = sum(1 for (stamp,) in db.query(HintEvent.created_at)
                .filter(HintEvent.user_id == user.id, HintEvent.created_at >= lo, HintEvent.created_at < hi)
                if (d := clock.local_date(user, stamp)) and start <= d <= end)

    streak = streaks.streak_summary(db, user, now)
    active = len(streaks.active_days(db, user, start, end))
    focus = [f["topic"] for f in (plan.focus_topics or [])]

    improved, needs_work = [], []
    if prog["total"] and prog["percent"] >= 70:
        improved.append(f"You completed {prog['done']} of {prog['total']} planned tasks ({prog['percent']}%).")
    for t in focus:
        if solved_by_topic.get(t):
            improved.append(f"Progress in {plans_label(t)}: {solved_by_topic[t]} problem{'s' if solved_by_topic[t] != 1 else ''} solved.")
    if streak["current_streak"] >= 3:
        improved.append(f"You have a {_days(streak['current_streak'])} streak going.")
    if prog["total"] and prog["percent"] < 50:
        needs_work.append(f"Only {prog['done']} of {prog['total']} tasks were done ({prog['percent']}%).")
    stalled = [t for t in focus if not solved_by_topic.get(t)]
    for t in stalled:
        needs_work.append(f"No {plans_label(t)} problems solved, so it is still a weak spot.")
    if solved_total and hints > 2 * solved_total:
        needs_work.append(f"You used {hints} hints for {solved_total} solved problems. Try the first hint only before the next one.")
    if not improved and not needs_work:
        improved.append("A quiet week: every bit of practice counts, keep going.")

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "reviewed_plan_id": plan.id,
        "tasks": prog,
        "solved_total": solved_total,
        "solved_by_topic": solved_by_topic,
        "hints_used": hints,
        "active_days": active,
        "streak": {"current": streak["current_streak"], "longest": streak["longest_streak"]},
        "improved": improved,
        "needs_work": needs_work,
        "carry_topics": stalled[:2],
        "lighter": bool(prog["total"] and prog["percent"] < 40),
    }


def plans_label(topic: str) -> str:
    from agent.planner import label
    return label(topic)


def weekly_review(db: Session, user: User, now: Optional[datetime] = None, llm: Optional[Callable] = None) -> StudyPlan:
    """Review the current plan and store next week's schedule as a PROPOSED plan (nothing is replaced yet)."""
    from agent.planner import create_plan

    plan = plans.get_active_plan(db, user.id)
    if plan is None:
        raise NothingToReview("There is no study plan to review yet. Generate a plan first.")
    stats = review_stats(db, user, plan, now)
    t = stats["tasks"]
    stats["narrative"] = (
        f"This week you completed {t['done']} of {t['total']} planned tasks, solved {stats['solved_total']} "
        f"problem{'' if stats['solved_total'] == 1 else 's'} and were active on {stats['active_days']} day"
        f"{'' if stats['active_days'] == 1 else 's'}."
        + (" Next week is lighter so it is easier to keep up." if stats["lighter"] else "")
    )
    return create_plan(
        db, user, goal=plan.goal, minutes_per_day=plan.minutes_per_day,
        review={"lighter": stats["lighter"], "carry_topics": stats["carry_topics"], "completion": t["percent"]},
        status="proposed", review_payload=stats, llm=llm,
    )


def confirm_review(db: Session, user: User) -> StudyPlan:
    proposed = plans.get_proposed_plan(db, user.id)
    if proposed is None:
        raise FollowupError("There is no proposed plan to confirm. Start the weekly review first.")
    for old in db.query(StudyPlan).filter(StudyPlan.user_id == user.id, StudyPlan.status == "active"):
        old.status = "archived"
    proposed.status = "active"
    db.commit()
    db.refresh(proposed)
    return proposed


def discard_review(db: Session, user: User) -> bool:
    proposed = plans.get_proposed_plan(db, user.id)
    if proposed is None:
        return False
    db.query(DailyTask).filter(DailyTask.plan_id == proposed.id).delete()
    db.delete(proposed)
    db.commit()
    return True


# ── notifications + cron ──────────────────────────────────────────────────────
def add_notification(db: Session, user_id: int, kind: str, message: str, dedupe_key: Optional[str] = None) -> bool:
    """True if a NEW row was created (False = the same nudge already exists for this key)."""
    if dedupe_key and db.query(Notification).filter(
            Notification.user_id == user_id, Notification.dedupe_key == dedupe_key).first():
        return False
    try:
        with db.begin_nested():
            db.add(Notification(user_id=user_id, type=kind, message=message, dedupe_key=dedupe_key))
    except IntegrityError:
        return False
    return True


def run_daily_nudges(db: Session, slot: str, now: Optional[datetime] = None,
                     send: Optional[Callable[[str, str, str], bool]] = None) -> dict:
    """
    For every user with an active plan: create an in-app notification (and, when the user opted in
    and a provider is configured, send an email). Safe to call twice: a nudge is created once per
    user + slot + local day. Never fails because of email problems.
    """
    send = send or emailer.send_email
    configured = emailer.email_configured()
    summary = {"slot": slot, "users_checked": 0, "notifications_created": 0, "emails_sent": 0,
               "emails_failed": 0, "email_configured": configured}

    user_ids = [uid for (uid,) in db.query(StudyPlan.user_id).filter(StudyPlan.status == "active").distinct()]
    for uid in user_ids:
        user = db.get(User, uid)
        plan = plans.get_active_plan(db, uid)
        if user is None or plan is None:
            continue
        summary["users_checked"] += 1
        today = clock.local_today(user, now)
        messages = []                                     # (type, dedupe_key, subject, text)

        if today > plan.week_start + timedelta(days=6):
            if slot == "morning":
                messages.append(("weekly_review", f"weekly_review:{plan.id}", "Your weekly review is ready",
                                 "Your plan week is over. Open the Coach to see your weekly review and next week's schedule."))
        else:
            info = plans.today_tasks(db, user, now)
            pending = [t for t in info["tasks"] if t["status"] == "pending"]
            sm = streaks.streak_summary(db, user, now)
            if pending and slot == "morning":
                titles = "; ".join(t["title"] for t in pending[:3])
                messages.append(("nudge", f"morning:{today.isoformat()}", "Today's study tasks",
                                 f"Good morning! You have {_tasks(len(pending))} today: {titles}."))
            elif pending and slot == "evening" and not sm["active_today"]:
                text = (f"Save your {_days(sm['current_streak'])} streak: finish just one task today."
                        if sm["current_streak"] else
                        f"You still have {_tasks(len(pending))} pending today. One task is enough to start a streak.")
                messages.append(("nudge", f"evening:{today.isoformat()}", "Keep your streak alive", text))

        for kind, key, subject, text in messages:
            if add_notification(db, uid, kind, text, key):
                summary["notifications_created"] += 1
                if configured and user.notify_email and user.email:
                    if send(user.email, subject, text + "\n\nOpen AI Coding Coach to continue."):
                        summary["emails_sent"] += 1
                    else:
                        summary["emails_failed"] += 1
    db.commit()
    return summary
