"""DB-level helpers for the Problems feature, shared by the API router and the CLI scripts."""
import logging
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import Attempt, Problem, TopicProgress, UserProblem
from problem_utils import map_topics, normalize_difficulty, primary_topic, slugify

log = logging.getLogger(__name__)

STATUSES = ("todo", "attempted", "solved")


class ProblemExists(Exception):
    """A problem with the same slug already exists."""


def create_custom_problem(db: Session, *, title: str, difficulty: str, topics: Iterable[str],
                          description: str, url: Optional[str] = None) -> Problem:
    """Add one hand-written problem (source="custom"). Raises ValueError / ProblemExists."""
    title = (title or "").strip()
    description = (description or "").strip()
    norm_difficulty = normalize_difficulty(difficulty)
    if not title:
        raise ValueError("title is required")
    if not description:
        raise ValueError("description is required")
    if norm_difficulty is None:
        raise ValueError("difficulty must be Easy, Medium or Hard")

    slug = slugify(title)
    if db.query(Problem).filter(Problem.slug == slug).first():
        raise ProblemExists(f"A problem with slug '{slug}' already exists")

    problem = Problem(
        title=title,
        slug=slug,
        difficulty=norm_difficulty,
        topics=map_topics(topics),   # raw LeetCode names or app names both work
        description=description,
        url=(url or "").strip() or None,
        acceptance_rate=None,
        source="custom",
    )
    db.add(problem)
    try:
        db.commit()
    except IntegrityError:           # lost a race on the unique slug
        db.rollback()
        raise ProblemExists(f"A problem with slug '{slug}' already exists")
    db.refresh(problem)
    return problem


def get_or_create_user_problem(db: Session, user_id: int, problem_id: int) -> UserProblem:
    """The (user, problem) row; safe if two requests race to create it (unique constraint)."""
    def lookup():
        return db.query(UserProblem).filter(
            UserProblem.user_id == user_id, UserProblem.problem_id == problem_id
        ).first()

    up = lookup()
    if up is not None:
        return up
    up = UserProblem(user_id=user_id, problem_id=problem_id, status="todo",
                     attempts_count=0, hints_used=0)
    try:
        with db.begin_nested():      # savepoint: a duplicate only rolls back this insert
            db.add(up)
    except IntegrityError:
        up = lookup()
    return up


def record_manual_solve(db: Session, user_id: int, problem: Problem) -> None:
    """
    "I solved it elsewhere": count it in the legacy tables so Topic Tracker / Progress
    stay consistent. Counted as one accepted attempt (count+1 AND total_attempts+1) so
    TopicProgress acceptance_rate (count / total_attempts) can never exceed 1.
    Does not commit.
    """
    topic = primary_topic(problem.topics)
    db.add(Attempt(
        user_id=user_id,
        question=problem.title,
        code=None,
        topic=topic,
        difficulty=problem.difficulty.lower(),
        time_complexity=None,
        space_complexity=None,
        bugs_found=0,
    ))
    tp = db.query(TopicProgress).filter(
        TopicProgress.user_id == user_id, TopicProgress.topic == topic
    ).first()
    if tp:
        tp.count = (tp.count or 0) + 1
        tp.total_attempts = (tp.total_attempts or 0) + 1
    else:
        db.add(TopicProgress(user_id=user_id, topic=topic, count=1, total_attempts=1))


def attach_problem_ids(db: Session, similar: list) -> list:
    """
    Add `problem_id` (None if unknown) to /recommend results by matching titles, so the
    frontend can link to /problems/{id}. Must never break /recommend: on any DB error
    (e.g. migration not run yet) the items are returned with problem_id=None.
    """
    items = [dict(q) for q in similar]
    try:
        titles = [str(q.get("title", "")).lower() for q in items]
        rows = db.query(Problem.id, Problem.title).filter(
            func.lower(Problem.title).in_(titles)
        ).all()
        by_title = {title.lower(): pid for pid, title in rows}
        for q in items:
            q["problem_id"] = by_title.get(str(q.get("title", "")).lower())
    except Exception:
        log.exception("could not attach problem ids to /recommend results")
        db.rollback()
        for q in items:
            q["problem_id"] = None
    return items
