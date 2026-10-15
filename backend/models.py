from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, ForeignKey
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


class InterviewTurn(Base):
    __tablename__ = "interview_turns"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"), index=True)
    role = Column(String)                          # user | assistant | tool
    content = Column(Text, default="")
    tool_calls = Column(Text, nullable=True)       # JSON (assistant ke tool calls)
    tool_call_id = Column(String, nullable=True)   # tool role ke liye
    created_at = Column(DateTime, default=datetime.utcnow)


# Tables banao database mein
def create_tables():
    Base.metadata.create_all(engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
