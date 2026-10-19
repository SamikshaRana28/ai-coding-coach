from sqlalchemy import create_engine, inspect, text, Column, Integer, String, Float, DateTime, Date, Boolean, Text, JSON, ForeignKey, false
from sqlalchemy.engine import make_url
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv
from datetime import datetime
import os

load_dotenv()

# Falls back to the local dev DB used by docker-compose / the scripts, so
# nothing breaks when DATABASE_URL is not set.
DEFAULT_LOCAL_DATABASE_URL = "postgresql://postgres:password@localhost/coding_coach"

# Hosts that never need TLS (local dev, docker-compose service name).
_NO_SSL_HOSTS = {None, "", "localhost", "127.0.0.1", "::1", "db"}


def normalize_database_url(url: str) -> str:
    """
    - Accepts the legacy 'postgres://' scheme (some providers hand it out).
    - For remote Postgres hosts (e.g. Neon) adds sslmode=require when the URL
      doesn't already specify an sslmode. Neon rejects non-TLS connections.
    """
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    parsed = make_url(url)
    if (
        parsed.get_backend_name() == "postgresql"
        and "sslmode" not in parsed.query
        and parsed.host not in _NO_SSL_HOSTS
    ):
        parsed = parsed.update_query_dict({"sslmode": "require"})
        return parsed.render_as_string(hide_password=False)
    return url


DATABASE_URL = normalize_database_url(
    os.getenv("DATABASE_URL") or DEFAULT_LOCAL_DATABASE_URL
)


def build_engine(url: str):
    if url.startswith("sqlite"):
        # Used by the test-suite. A shared in-memory DB needs StaticPool.
        kwargs = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url or url in ("sqlite://", "sqlite:///"):
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)

    return create_engine(
        url,
        # Neon scales to zero and silently drops idle connections:
        # test each pooled connection before use, and recycle them regularly.
        pool_pre_ping=True,
        pool_recycle=int(os.getenv("DB_POOL_RECYCLE_SECONDS", "300")),
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
    )


engine = build_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# User table
# NOTE: the auth columns (password_hash, name, first_name, last_name, timezone)
# are all nullable so legacy rows stay valid. On an existing database they are
# added by Alembic migration 0001_auth_foundation (additive only).
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    email = Column(String, unique=True)   # always stored lowercase by the auth code
    created_at = Column(DateTime, default=datetime.utcnow)

    password_hash = Column(String, nullable=True)
    name = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    timezone = Column(String, nullable=True, default="Asia/Kolkata", server_default="Asia/Kolkata")
 # Part 6: opt-in for reminder emails (off unless the student turns it on in Settings)
    notify_email = Column(Boolean, nullable=False, default=False, server_default=false())
# Attempt table - har baar user code submit kare
class Attempt(Base):
    __tablename__ = "attempts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    question = Column(Text)
    code = Column(Text)
    topic = Column(String)        # arrays, graphs, dp etc
    difficulty = Column(String)   # easy, medium, hard
    time_complexity = Column(String)
    space_complexity = Column(String)
    bugs_found = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


# TopicProgress table - per-user, per-topic solved counts (dynamic, any topic name)
class TopicProgress(Base):
    __tablename__ = "topic_progress"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    topic = Column(String)        # any topic name - arrays, dp, "linked lists", etc.
    count = Column(Integer, default=0)
    total_attempts = Column(Integer, default=0)  # for acceptance_rate calc


# ── Interviewer Agent tables ───────────────────────────────────────────────
class WeakPattern(Base):
    """Interview + Coach ko jodne wali table"""
    __tablename__ = "weak_patterns"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)
    pattern = Column(String)                 # e.g. "sliding window"
    count = Column(Integer, default=1)       # kitni baar flag hua
    source = Column(String, default="interview")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)
    topic = Column(String)
    status = Column(String, default="active")      # active | finished | expired
    step_count = Column(Integer, default=0)        # candidate ke answers ki ginti
    asked_question_ids = Column(Text, default="[]")
    current_question_id = Column(String, nullable=True)
    hints_used = Column(Integer, default=0)
    scorecard = Column(Text, nullable=True)        # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    # Part 9 (interview mode): round = dsa | behavioral | sql | resume | mixed.
    # resume_text is wiped when the interview ends (or via DELETE /interview/{id}/resume).
    # delivery_metrics = JSON with AGGREGATE numbers only (eye contact %, pace...). No video/images, ever.
    round = Column(String, default="dsa", server_default="dsa")
    resume_text = Column(Text, nullable=True)
    delivery_metrics = Column(Text, nullable=True)


class InterviewTurn(Base):
    __tablename__ = "interview_turns"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"), index=True)
    role = Column(String)                          # user | assistant | tool
    content = Column(Text, default="")
    tool_calls = Column(Text, nullable=True)       # JSON (assistant ke tool calls)
    tool_call_id = Column(String, nullable=True)   # tool role ke liye
    created_at = Column(DateTime, default=datetime.utcnow)


from sqlalchemy import Float, JSON, UniqueConstraint  # noqa: E402


# Problem table - the browsable question bank (seeded from the LeetCode CSV, plus custom ones)
class Problem(Base):
    __tablename__ = "problems"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True, index=True)
    difficulty = Column(String, nullable=False, index=True)    # Easy / Medium / Hard
    topics = Column(JSON, nullable=False, default=list)        # app topics, primary first
    description = Column(Text, nullable=False, default="")
    url = Column(String, nullable=True)                        # optional external link
    acceptance_rate = Column(Float, nullable=True)             # percent, 0-100
    source = Column(String, nullable=False, default="leetcode", server_default="leetcode")  # leetcode / custom


# UserProblem table - one row per (user, problem): status + latest code
class UserProblem(Base):
    __tablename__ = "user_problems"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"), nullable=False)
    status = Column(String, nullable=False, default="todo", server_default="todo")  # todo / attempted / solved
    attempts_count = Column(Integer, nullable=False, default=0, server_default="0")
    hints_used = Column(Integer, nullable=False, default=0, server_default="0")
    last_code = Column(Text, nullable=True)
    solved_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "problem_id", name="uq_user_problems_user_problem"),)
# CoachMessage table - chat history with the Coach agent


# HintEvent table (Part 4) - one row per (user, problem, level): the hint text that was
# shown. It doubles as the cache, so clicking Hint again never calls the LLM again and
# the hint a student saw stays the same when they reopen the problem.
class HintEvent(Base):
    __tablename__ = "hint_events"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="CASCADE"), nullable=False, index=True)
    level = Column(Integer, nullable=False)          # 1 (nudge) .. 3 (pseudo-code outline)
    hint_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "problem_id", "level", name="uq_hint_events_user_problem_level"),)
class CoachMessage(Base):
    __tablename__ = "coach_messages"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    role = Column(String, nullable=False)        # user / assistant / tool
    content = Column(Text, nullable=False, default="")
    tool_calls = Column(JSON, nullable=True)     # tool requests / tool info / tools_used (see coach_router)
    created_at = Column(DateTime, default=datetime.utcnow)
# ── Part 5: study plan, daily tasks, streak ───────────────────────────────────
class StudyPlan(Base):
    __tablename__ = "study_plans"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    week_start = Column(Date, nullable=False)           # first day of the 7-day plan (user's local date)
    status = Column(String, nullable=False, default="active")   # active / archived / proposed (weekly review, not confirmed yet)
    summary = Column(Text, nullable=True)
    focus_topics = Column(JSON, nullable=True)          # [{topic, reason, patterns: [...]}]
    goal = Column(Text, nullable=True)                  # what the student asked for ("interview in 4 weeks")
    minutes_per_day = Column(Integer, nullable=True)
    source = Column(String, nullable=True)              # "llm" or "rules": who arranged the tasks
    review = Column(JSON, nullable=True)                # weekly-review numbers, only on proposed plans
    created_at = Column(DateTime, default=datetime.utcnow)


class DailyTask(Base):
    __tablename__ = "daily_tasks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("study_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)                 # the student's local calendar day
    kind = Column(String, nullable=False)               # problem / revise / concept
    problem_id = Column(Integer, ForeignKey("problems.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending / done / skipped
    completed_at = Column(DateTime, nullable=True)      # naive UTC


class UserStreak(Base):
    __tablename__ = "user_streaks"
    user_id = Column(Integer, primary_key=True)
    current_streak = Column(Integer, nullable=False, default=0)
    longest_streak = Column(Integer, nullable=False, default=0)
    last_active_date = Column(Date, nullable=True)      # last local day with a completed task / solved problem


# ── Part 6: check-ins and notifications ───────────────────────────────────────
class CheckIn(Base):
    __tablename__ = "checkins"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False)                 # local day; one check-in per user per day
    mood = Column(Integer, nullable=True)               # 1 (bad) .. 5 (great)
    note = Column(Text, nullable=True)
    tasks_done = Column(Integer, nullable=False, default=0)
    tasks_total = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_checkins_user_date"),)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    type = Column(String, nullable=False)               # nudge / checkin / weekly_review
    message = Column(Text, nullable=False)
    read = Column(Boolean, nullable=False, default=False, server_default=false())
    dedupe_key = Column(String, nullable=True)          # e.g. "morning:2026-10-19": a cron retry never doubles a nudge
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_notifications_user_dedupe"),)


# Columns that were added to EXISTING tables after the first release. create_all() only creates
# missing tables, never missing columns, so without this a database that has not run
# `alembic upgrade head` yet would crash on every login. Idempotent and additive only.
_ADDED_COLUMNS = [
    ("users", "notify_email", "BOOLEAN NOT NULL DEFAULT false"),
    ("interview_sessions", "round", "VARCHAR DEFAULT 'dsa'"),
    ("interview_sessions", "resume_text", "TEXT"),
    ("interview_sessions", "delivery_metrics", "TEXT"),
]


def ensure_columns(bind=None):
    bind = bind or engine
    insp = inspect(bind)
    for table, column, ddl in _ADDED_COLUMNS:
        if not insp.has_table(table):
            continue
        if column in {c["name"] for c in insp.get_columns(table)}:
            continue
        default = "0" if bind.dialect.name == "sqlite" else None
        statement = f'ALTER TABLE {table} ADD COLUMN {column} ' + (
            ddl.replace("false", default) if default else ddl)
        with bind.begin() as conn:
            conn.execute(text(statement))
# Tables banao database mein
def create_tables():
    Base.metadata.create_all(engine)
    ensure_columns(engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
