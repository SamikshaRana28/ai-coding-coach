import os
import sys
import types
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# Never touch a real database from the tests (models.py reads this at import time).
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.pop("ADMIN_TOKEN", None)
# Auth: a long-enough secret, and rate limiting off (test_auth turns it on for one test).
os.environ["JWT_SECRET"] = "test-secret-for-pytest-only-0123456789abcdef"
os.environ["RATE_LIMIT_ENABLED"] = "false"

# ml/recommender.py downloads/loads a sentence-transformer at import time. The API
# tests don't need the real model, so stub it (unless something already imported it).
if "ml.recommender" not in sys.modules:
    _stub = types.ModuleType("ml.recommender")
    _stub.get_similar_questions = lambda title, top_n=3: []
    sys.modules["ml.recommender"] = _stub


SEED_ROWS = [
    {"title": "Two Sum", "slug": "two-sum", "difficulty": "Easy", "topics": ["arrays"],
     "description": "Find two numbers that add up to target.", "url": "https://leetcode.com/problems/two-sum",
     "acceptance_rate": 46.7},
    {"title": "Add Two Numbers", "slug": "add-two-numbers", "difficulty": "Medium", "topics": ["math"],
     "description": "Add two numbers stored as linked lists.", "url": None, "acceptance_rate": 35.7},
    {"title": "Longest Palindromic Substring", "slug": "longest-palindromic-substring", "difficulty": "Medium",
     "topics": ["dp", "strings"], "description": "Return the longest palindromic substring.", "url": None,
     "acceptance_rate": 30.6},
    {"title": "Number of Islands", "slug": "number-of-islands", "difficulty": "Medium", "topics": ["graphs"],
     "description": "Count islands in a grid.", "url": None, "acceptance_rate": 48.0},
    {"title": "Binary Tree Inorder Traversal", "slug": "binary-tree-inorder-traversal", "difficulty": "Easy",
     "topics": ["trees"], "description": "Inorder traversal.", "url": None, "acceptance_rate": 70.1},
    {"title": "Merge k Sorted Lists", "slug": "merge-k-sorted-lists", "difficulty": "Hard", "topics": ["others"],
     "description": "Merge k sorted linked lists.", "url": None, "acceptance_rate": 40.2},
]


class FakeReview:
    """Stands in for the LLM: returns a canned review and records how it was called."""

    def __init__(self):
        from analysis import AnalyzeResponse
        self._cls = AnalyzeResponse
        self.bugs = "No bugs found"
        self.error = None
        self.calls = []

    def __call__(self, question, code, language="python", statement=None):
        self.calls.append({"question": question, "code": code, "language": language, "statement": statement})
        if self.error:
            raise self.error
        return self._cls(
            time_complexity="O(n)", space_complexity="O(1)", bugs=self.bugs,
            better_approach="This is optimal", similar_questions="- something similar",
            interviewer_questions="1. q1\n2. q2\n3. q3",
        )


# ── auth helpers (used by test_auth.py, test_problems.py, test_hints.py) ─────
def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def signup(client, email="alice@example.com", password="correct-horse-1", name="Alice Smith"):
    """POST /auth/signup and return the raw response."""
    return client.post("/auth/signup", json={"email": email, "password": password, "name": name})


def _build_env(monkeypatch):
    """In-memory SQLite shared by the app (via dependency override) and the test's own sessions."""
    from types import SimpleNamespace

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import main
    import models

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[models.get_db] = override_get_db
    return SimpleNamespace(main=main, Session=Session)


def _register(client, email, name="Test User", password="correct-horse-1"):
    """Sign a user up through the real endpoint -> (user_dict, auth headers)."""
    resp = signup(client, email=email, password=password, name=name)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["user"], auth_header(body["access_token"])


@pytest.fixture()
def main_module():
    """The module that owns the Groq `client` (analysis.py; /analyze calls it through run_analysis)."""
    import analysis
    return analysis


def _reset_real_db():
    """Empty, freshly-created tables on the app's real engine (SQLite in memory in tests)."""
    import models

    models.Base.metadata.drop_all(models.engine)
    models.Base.metadata.create_all(models.engine)


@pytest.fixture()
def client():
    """
    TestClient on the app's real engine/SessionLocal (no dependency override), with clean tables.
    Shared by test_auth.py and test_interview.py; those tests also open models.SessionLocal()
    themselves, so the app and the tests must see the same database.
    """
    from fastapi.testclient import TestClient

    import main

    main.app.dependency_overrides.clear()
    _reset_real_db()
    yield TestClient(main.app)
    _reset_real_db()


@pytest.fixture()
def db(client):
    """A session on the same database the `client` fixture uses."""
    import models

    session = models.SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def make_user(client):
    """make_user(email, name, password) -> (user_dict, auth_headers). Signs up via the API."""
    counter = {"n": 0}

    def _make(email=None, name="Test User", password="correct-horse-1"):
        counter["n"] += 1
        return _register(client, email or f"user{counter['n']}@example.com", name, password)

    return _make


@pytest.fixture()
def api(monkeypatch):
    """
    TestClient on an in-memory SQLite DB with 6 seeded problems and a fake LLM.

    Two real users are created through /auth/signup (ids 1 and 2):
      * api.client sends user 1's JWT by default,
      * api.h1 / api.h2 are the Authorization headers of user 1 / user 2
        (pass headers=api.h2 to act as the second user).
    """
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from routers import problems as problems_router
    from scripts.seed_problems import seed

    env = _build_env(monkeypatch)
    main = env.main

    fake = FakeReview()
    monkeypatch.setattr(problems_router, "run_analysis", fake)
    monkeypatch.setattr(main, "run_analysis", fake)

    # fresh hint rate limiter per test (it is per user id in memory, and every test reuses ids 1 and 2)
    from coach_router import RateLimiter
    monkeypatch.setattr(problems_router, "hint_limiter", RateLimiter(1000))
    from routers import followups as followups_router, plan as plan_router
    monkeypatch.setattr(plan_router, "plan_limiter", RateLimiter(1000))
    monkeypatch.setattr(followups_router, "review_limiter", RateLimiter(1000))

    db = env.Session()
    seed(db, [dict(r) for r in SEED_ROWS])
    db.close()

    test_client = TestClient(main.app)
    _, h1 = _register(test_client, "one@example.com", "User One")
    _, h2 = _register(test_client, "two@example.com", "User Two")
    test_client.headers.update(h1)       # default identity = user 1

    yield SimpleNamespace(client=test_client, Session=env.Session, llm=fake, main=main, h1=h1, h2=h2)
    main.app.dependency_overrides.clear()
# ── Part 5/6 helpers ──────────────────────────────────────────────────────────
class ClockControl:
    """Freezes clock.utcnow(). Default: Monday 2026-10-19 04:00 UTC = 09:30 in Asia/Kolkata (morning)."""

    def __init__(self):
        from datetime import datetime
        self.value = datetime(2026, 10, 19, 4, 0)

    def set(self, year, month, day, hour=4, minute=0):
        from datetime import datetime
        self.value = datetime(year, month, day, hour, minute)

    def advance(self, **kwargs):
        from datetime import timedelta
        self.value += timedelta(**kwargs)


@pytest.fixture()
def ctl(monkeypatch):
    import clock

    control = ClockControl()
    monkeypatch.setattr(clock, "utcnow", lambda: control.value)
    return control


def seed_bank(api, per_topic=12):
    """A realistic question bank: `per_topic` problems for each of the 7 app topics (Easy/Medium/Hard mix)."""
    from scripts.seed_problems import seed

    diffs = ["Easy", "Easy", "Easy", "Medium", "Medium", "Medium", "Medium", "Hard", "Easy", "Medium", "Medium", "Hard"]
    rows = []
    for topic in ["arrays", "dp", "graphs", "trees", "strings", "math", "others"]:
        for i in range(per_topic):
            rows.append({"title": f"{topic.title()} Problem {i + 1}", "slug": f"bank-{topic}-{i + 1}",
                         "difficulty": diffs[i % len(diffs)], "topics": [topic],
                         "description": f"Practice problem {i + 1} about {topic}.", "url": None,
                         "acceptance_rate": 30.0 + i * 3})
    db = api.Session()
    seed(db, rows)
    db.close()


def give_stats(api, user_id, **per_topic):
    """TopicProgress rows: give_stats(api, 1, arrays=(20, 22), graphs=(1, 6)) = (solved, attempts)."""
    from models import TopicProgress

    db = api.Session()
    for topic, (solved, attempts) in per_topic.items():
        db.add(TopicProgress(user_id=user_id, topic=topic, count=solved, total_attempts=attempts))
    db.commit()
    db.close()