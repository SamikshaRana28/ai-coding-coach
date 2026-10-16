"""
Problems API: browse the question bank, open a problem, submit code for AI review,
track per-user status.

Auth note: the app has no login yet (every page hard-codes user 1). All "per user"
behaviour goes through `current_user_id`, which reads the X-User-Id header and
defaults to 1, so real auth later only has to replace that one dependency.
"""
import math
import os
import secrets
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import String, and_, cast, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, defer

from analysis import bugs_clean, record_attempt, run_analysis
from models import Problem, UserProblem, get_db
from problem_utils import normalize_difficulty, primary_topic
from problems_service import (
    STATUSES, ProblemExists, create_custom_problem, get_or_create_user_problem,
    record_manual_solve,
)

router = APIRouter(tags=["problems"])


# ── dependencies ───────────────────────────────────────────────────────────────
def current_user_id(x_user_id: Optional[int] = Header(default=None)) -> int:
    """The acting user. No auth yet: X-User-Id header, defaulting to 1 like the rest of the app."""
    if x_user_id is None:
        return 1
    if x_user_id < 1:
        raise HTTPException(status_code=400, detail="X-User-Id must be a positive integer")
    return x_user_id


def require_admin(x_admin_token: Optional[str] = Header(default=None)) -> None:
    """Admin endpoints are disabled unless ADMIN_TOKEN is set, then need a matching X-Admin-Token."""
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="Admin endpoints are disabled: set ADMIN_TOKEN on the server")
    if not x_admin_token or not secrets.compare_digest(x_admin_token.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Invalid admin token")


# ── schemas ────────────────────────────────────────────────────────────────────
class SubmitRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20000)
    language: Literal["python", "javascript", "java", "cpp"] = "python"

    @field_validator("code")
    @classmethod
    def code_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("code must not be empty")
        return v


class CustomProblemIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    difficulty: str                        # Easy / Medium / Hard (case-insensitive)
    topics: list[str] = Field(default_factory=list, max_length=10)
    description: str = Field(min_length=1, max_length=20000)
    url: Optional[str] = Field(default=None, max_length=500)


# ── helpers ────────────────────────────────────────────────────────────────────
def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() + "Z" if dt else None    # stored as naive UTC


def _like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _problem_or_404(db: Session, problem_id: int) -> Problem:
    problem = db.get(Problem, problem_id)
    if problem is None:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem


def _list_item(p: Problem, up: Optional[UserProblem]) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "slug": p.slug,
        "difficulty": p.difficulty,
        "topics": p.topics or [],
        "acceptance_rate": p.acceptance_rate,
        "source": p.source,
        "url": p.url,
        "status": up.status if up else "todo",
        "attempts_count": up.attempts_count if up else 0,
    }


def _detail(p: Problem, up: Optional[UserProblem]) -> dict:
    return {
        **_list_item(p, up),
        "description": p.description,
        "last_code": up.last_code if up else None,
        "hints_used": up.hints_used if up else 0,
        "solved_at": _iso(up.solved_at) if up else None,
    }


# ── endpoints ──────────────────────────────────────────────────────────────────
@router.get("/problems")
def list_problems(
    search: Optional[str] = Query(None, max_length=100),
    difficulty: Optional[str] = Query(None),
    topic: Optional[str] = Query(None, max_length=50),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user_id: int = Depends(current_user_id),
):
    """Paginated problem list with the calling user's status on each row."""
    search = (search or "").strip()
    topic = (topic or "").strip().lower()
    difficulty_raw = (difficulty or "").strip()
    status_raw = (status or "").strip().lower()

    difficulty_norm = None
    if difficulty_raw:
        difficulty_norm = normalize_difficulty(difficulty_raw)
        if difficulty_norm is None:
            raise HTTPException(status_code=422, detail="difficulty must be Easy, Medium or Hard")
    if status_raw and status_raw not in STATUSES:
        raise HTTPException(status_code=422, detail="status must be one of: " + ", ".join(STATUSES))

    # LEFT JOIN so problems the user never touched still show up (as "todo")
    q = (
        db.query(Problem, UserProblem)
        .outerjoin(UserProblem, and_(UserProblem.problem_id == Problem.id, UserProblem.user_id == user_id))
        .options(defer(Problem.description), defer(UserProblem.last_code))  # keep list rows light
    )
    if search:
        q = q.filter(Problem.title.ilike(f"%{_like_escape(search)}%", escape="\\"))
    if difficulty_norm:
        q = q.filter(Problem.difficulty == difficulty_norm)
    if topic:
        # topics is a JSON list; match the quoted token so "dp" can't match inside another word
        q = q.filter(cast(Problem.topics, String).like(f'%"{_like_escape(topic)}"%', escape="\\"))
    if status_raw:
        q = q.filter(func.coalesce(UserProblem.status, "todo") == status_raw)

    total = q.count()
    rows = q.order_by(Problem.id).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_list_item(p, up) for p, up in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, math.ceil(total / page_size)),
    }


@router.get("/problems/{problem_id}")
def get_problem(problem_id: int, db: Session = Depends(get_db),
                user_id: int = Depends(current_user_id)):
    problem = _problem_or_404(db, problem_id)
    up = db.query(UserProblem).filter(
        UserProblem.user_id == user_id, UserProblem.problem_id == problem_id
    ).first()
    return _detail(problem, up)


@router.post("/problems/{problem_id}/submit")
def submit_problem(problem_id: int, body: SubmitRequest, db: Session = Depends(get_db),
                   user_id: int = Depends(current_user_id)):
    """
    AI-review the code (same logic as /analyze), then in ONE transaction:
    save last_code, bump attempts_count, set status (solved when the review finds no
    bugs), and write the legacy Attempt + TopicProgress rows.
    If the AI call fails nothing is written.
    """
    problem = _problem_or_404(db, problem_id)

    review = run_analysis(problem.title, body.code, body.language, statement=problem.description)
    clean = bugs_clean(review.bugs)

    try:
        up = get_or_create_user_problem(db, user_id, problem.id)
        was_solved = up.status == "solved"
        newly_solved = clean and not was_solved

        record_attempt(
            db,
            user_id=user_id,
            question=problem.title,
            code=body.code,
            topic=primary_topic(problem.topics),
            difficulty=problem.difficulty.lower(),   # Attempt.difficulty is lower-case (easy/medium/hard)
            result=review,
            count_solved=newly_solved,               # a problem counts once towards TopicProgress
        )

        up.last_code = body.code
        up.attempts_count = (up.attempts_count or 0) + 1
        if newly_solved:
            up.status = "solved"
            up.solved_at = datetime.utcnow()
        elif not was_solved:
            up.status = "attempted"                  # solved never goes back down
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "review": review.model_dump(),
        "status": up.status,
        "attempts_count": up.attempts_count,
        "hints_used": up.hints_used,
        "clean": clean,                  # this submission's review found no bugs
        "newly_solved": newly_solved,    # ...and it flipped the problem to solved
    }


@router.post("/problems/{problem_id}/mark-solved")
def mark_solved(problem_id: int, db: Session = Depends(get_db),
                user_id: int = Depends(current_user_id)):
    """Manual 'I solved it' (e.g. solved on LeetCode). Idempotent."""
    problem = _problem_or_404(db, problem_id)
    try:
        up = get_or_create_user_problem(db, user_id, problem.id)
        newly_solved = up.status != "solved"
        if newly_solved:
            up.status = "solved"
            up.solved_at = datetime.utcnow()
            record_manual_solve(db, user_id, problem)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": up.status,
        "attempts_count": up.attempts_count,
        "hints_used": up.hints_used,
        "newly_solved": newly_solved,
        "solved_at": _iso(up.solved_at),
    }


@router.post("/admin/problems", status_code=201, dependencies=[Depends(require_admin)])
def admin_add_problem(body: CustomProblemIn, db: Session = Depends(get_db)):
    """Add one custom problem. Needs ADMIN_TOKEN on the server and an X-Admin-Token header."""
    try:
        problem = create_custom_problem(
            db, title=body.title, difficulty=body.difficulty, topics=body.topics,
            description=body.description, url=body.url,
        )
    except ProblemExists as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _detail(problem, None)
