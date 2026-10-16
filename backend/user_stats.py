"""
user_stats.py - one place that turns a user's DB rows into the numbers the app uses.

Used by:
  * GET /topic-stats/{user_id}          (topic_stats)
  * the Coach agent tools               (topic_stats, build_user_stats)
"""
from sqlalchemy.orm import Session

from models import TopicProgress

CORE_TOPICS = ["arrays", "graphs", "dp", "trees", "strings", "math"]   # topics the ML models know
STAT_KEYS = [f"{t}_solved" for t in CORE_TOPICS] + ["avg_attempts", "acceptance_rate"]


def topic_stats(db: Session, user_id: int) -> dict:
    """Solved-count per topic (any topic name) + overall acceptance. Same output as before."""
    rows = db.query(TopicProgress).filter(TopicProgress.user_id == user_id).all()
    total_attempts = sum(r.total_attempts for r in rows)
    acceptance_rate = (
        sum(r.count for r in rows) / total_attempts if total_attempts > 0 else 0
    )
    return {
        "user_id": user_id,
        "topics": {r.topic: r.count for r in rows},
        "acceptance_rate": round(acceptance_rate, 3),
        "total_attempts": total_attempts,
    }


def build_user_stats(db: Session, user_id: int) -> dict:
    """
    The 8 features calculate_readiness_score / predict_weak_topic expect
    (arrays_solved ... math_solved, avg_attempts, acceptance_rate),
    plus total_attempts / total_solved for context.

    avg_attempts = attempts per solved problem, clamped to the model's 1-5 scale.
    """
    rows = db.query(TopicProgress).filter(TopicProgress.user_id == user_id).all()
    by_topic = {r.topic.strip().lower(): r.count for r in rows}
    total_attempts = sum(r.total_attempts for r in rows)
    total_solved = sum(r.count for r in rows)

    stats = {f"{t}_solved": int(by_topic.get(t, 0)) for t in CORE_TOPICS}
    stats["acceptance_rate"] = round(total_solved / total_attempts, 3) if total_attempts else 0.0
    if total_solved:
        stats["avg_attempts"] = round(min(5.0, max(1.0, total_attempts / total_solved)), 2)
    else:
        stats["avg_attempts"] = 5.0          # nothing solved yet -> worst efficiency
    stats["total_attempts"] = int(total_attempts)
    stats["total_solved"] = int(total_solved)
    return stats
