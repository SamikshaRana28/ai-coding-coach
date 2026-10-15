"""
Shared test setup. Runs BEFORE any test module imports `main`/`models`.

* Forces an in-memory SQLite DB so tests can never touch a real/Neon database,
  even if a developer has DATABASE_URL in their shell or .env.
* Sets a test-only JWT secret (not a real secret) and disables rate limiting
  (the rate-limit test turns it back on for itself).
* Stubs ml.recommender: the real one loads ml/questions_df.pkl and downloads the
  fastembed model at import time - slow, needs network, and irrelevant to auth tests.
"""
import asyncio
import os
import sys
import types

import httpx
import pytest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-only-secret-not-for-production-0123456789"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ.pop("TRUSTED_PROXY_HOPS", None)
os.environ.pop("CORS_ORIGINS", None)

_fake_recommender = types.ModuleType("ml.recommender")
_fake_recommender.get_similar_questions = lambda title, top_n=3: []
sys.modules.setdefault("ml.recommender", _fake_recommender)


class ApiClient:
    """
    Tiny sync wrapper over httpx's ASGI transport. Used instead of Starlette's
    TestClient because the pinned httpx (0.28) is not compatible with the
    TestClient shipped with the pinned FastAPI (0.111).
    """

    def __init__(self, app):
        self.app = app

    def request(self, method, url, **kwargs):
        async def go():
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
                return await c.request(method, url, **kwargs)

        return asyncio.run(go())

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)


@pytest.fixture(scope="session")
def main_module():
    import main  # noqa: WPS433 (import after env is prepared)

    return main


@pytest.fixture()
def clean_db(main_module):
    """Empty tables before and after the test (requested via `client` / `db`)."""
    from models import Base, engine

    def wipe():
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())

    wipe()
    yield
    wipe()


@pytest.fixture()
def client(main_module, clean_db):
    return ApiClient(main_module.app)


@pytest.fixture()
def db(main_module, clean_db):
    from models import SessionLocal

    with SessionLocal() as session:
        yield session


def signup(client, email="alice@example.com", password="correct-horse-1", name="Alice Smith", **extra):
    return client.post("/auth/signup", json={"email": email, "password": password, "name": name, **extra})


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def make_user(client):
    """Signs a user up and returns (user_dict, headers)."""

    def _make(email="alice@example.com", name="Alice Smith", password="correct-horse-1"):
        resp = signup(client, email=email, password=password, name=name)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        return body["user"], auth_header(body["access_token"])

    return _make
