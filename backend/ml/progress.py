"""
progress.py — Weekly readiness score time-series tracker
Reads from attempts table → computes score per week → stores in progress_history table
"""

from sqlalchemy import Column, Integer, Float, DateTime, String, text
from sqlalchemy.orm import Session
from models import get_db, Attempt, Base, engine
from ml.score import calculate_readiness_score
from datetime import datetime, timedelta
import random


# ── DB Model ─────────────────────────────────────────────────────────────────
class ProgressHistory(Base):
    __tablename__ = "progress_history"
    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, index=True)
    week_label = Column(String)   # e.g. "Week 1", "Jun 2"
    score      = Column(Float)
    arrays     = Column(Integer, default=0)
    graphs     = Column(Integer, default=0)
    dp         = Column(Integer, default=0)
    trees      = Column(Integer, default=0)
    strings    = Column(Integer, default=0)
    math       = Column(Integer, default=0)
    recorded_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(engine)


def get_or_generate_progress(user_id: int, db: Session) -> list[dict]:
    """
    Returns weekly progress for a user.
    If real data exists → computes from attempts.
    If not enough real data → seeds realistic demo progression.
    """
    real_progress = _compute_real_progress(user_id, db)

    if len(real_progress) >= 2:
        return real_progress

    # Seed demo data if user has no history yet
    existing = db.query(ProgressHistory).filter_by(user_id=user_id).count()
    if existing == 0:
        _seed_demo_progress(user_id, db)

    rows = (db.query(ProgressHistory)
              .filter_by(user_id=user_id)
              .order_by(ProgressHistory.recorded_at)
              .all())

    return [_row_to_dict(r) for r in rows]


def _compute_real_progress(user_id: int, db: Session) -> list[dict]:
    """Group real attempts by week and compute score per week."""
    attempts = (db.query(Attempt)
                  .filter(Attempt.user_id == user_id)
                  .order_by(Attempt.created_at)
                  .all())

    if not attempts:
        return []

    # Group by week
    weeks: dict[str, list] = {}
    for a in attempts:
        if a.created_at is None:
            continue
        # ISO week key
        week_key = a.created_at.strftime("%Y-W%W")
        weeks.setdefault(week_key, []).append(a)

    if len(weeks) < 2:
        return []

    result = []
    cumulative = {t: 0 for t in ["arrays", "graphs", "dp", "trees", "strings", "math"]}

    for i, (week_key, week_attempts) in enumerate(sorted(weeks.items())):
        # Count topics solved this week
        for a in week_attempts:
            topic = (a.topic or "arrays").lower().replace(" ", "_")
            if topic in cumulative:
                cumulative[topic] += 1

        score_data = calculate_readiness_score(
            cumulative["arrays"], cumulative["graphs"], cumulative["dp"],
            cumulative["trees"], cumulative["strings"], cumulative["math"],
            avg_attempts=2.0, acceptance_rate=0.6
        )

        # Convert week_key to readable label
        year, wnum = week_key.split("-W")
        week_start = datetime.strptime(f"{year}-W{wnum}-1", "%Y-W%W-%w")
        label = week_start.strftime("%b %d")

        result.append({
            "week": label,
            "score": score_data.get("score", 0),
            **{k: cumulative[k] for k in cumulative}
        })

    return result


def _seed_demo_progress(user_id: int, db: Session):
    """Seed 8 weeks of realistic upward-trending demo data."""
    base_date = datetime.utcnow() - timedelta(weeks=8)
    random.seed(user_id * 7)  # deterministic per user

    # Realistic growth curve: starts slow, accelerates mid-way
    score_curve = [18, 27, 34, 42, 51, 63, 71, 78]
    topic_growth = {
        "arrays":  [2, 4, 6, 9, 12, 15, 18, 22],
        "graphs":  [0, 1, 2, 3, 5,  7,  9,  11],
        "dp":      [0, 0, 1, 2, 4,  5,  7,  9],
        "trees":   [1, 2, 3, 5, 7,  9,  11, 13],
        "strings": [1, 2, 4, 6, 8,  10, 12, 14],
        "math":    [1, 2, 3, 4, 5,  6,  7,  8],
    }

    for i in range(8):
        week_date = base_date + timedelta(weeks=i)
        label = week_date.strftime("Week %d %b" if i == 0 else "%b %d")

        row = ProgressHistory(
            user_id=user_id,
            week_label=f"Week {i+1}",
            score=score_curve[i] + random.uniform(-2, 2),
            arrays=topic_growth["arrays"][i],
            graphs=topic_growth["graphs"][i],
            dp=topic_growth["dp"][i],
            trees=topic_growth["trees"][i],
            strings=topic_growth["strings"][i],
            math=topic_growth["math"][i],
            recorded_at=week_date,
        )
        db.add(row)

    db.commit()


def _row_to_dict(row: ProgressHistory) -> dict:
    return {
        "week":    row.week_label,
        "score":   round(row.score, 1),
        "arrays":  row.arrays,
        "graphs":  row.graphs,
        "dp":      row.dp,
        "trees":   row.trees,
        "strings": row.strings,
        "math":    row.math,
    }