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


@pytest.fixture()
def api(monkeypatch):
    """TestClient on an in-memory SQLite DB with 6 seeded problems and a fake LLM."""
    from types import SimpleNamespace

    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import main
    import models
    from routers import problems as problems_router
    from scripts.seed_problems import seed

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

    fake = FakeReview()
    monkeypatch.setattr(problems_router, "run_analysis", fake)
    monkeypatch.setattr(main, "run_analysis", fake)

    db = Session()
    seed(db, [dict(r) for r in SEED_ROWS])
    db.close()

    yield SimpleNamespace(client=TestClient(main.app), Session=Session, llm=fake, main=main)
    main.app.dependency_overrides.clear()
