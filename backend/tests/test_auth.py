"""Tests for Part 1: signup/login/me, token handling, data isolation, demo seed."""
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt

from tests.conftest import auth_header, signup

GENERIC = "Invalid email or password"


# ── signup ─────────────────────────────────────────────────────────────────
def test_signup_creates_user_and_returns_token(client, db):
    resp = signup(client, email="Alice@Example.com", name="Alice Smith")
    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer" and body["access_token"]
    user = body["user"]
    assert user["email"] == "alice@example.com"  # lowercased
    assert user["name"] == "Alice Smith"
    assert user["first_name"] == "Alice" and user["last_name"] == "Smith"
    assert user["timezone"] == "Asia/Kolkata"
    assert "password" not in user and "password_hash" not in user


def test_signup_accepts_first_and_last_name(client):
    resp = client.post(
        "/auth/signup",
        json={"email": "b@example.com", "password": "longenough1", "first_name": "Bob", "last_name": "Jones"},
    )
    assert resp.status_code == 201
    assert resp.json()["user"]["name"] == "Bob Jones"


def test_password_is_stored_as_argon2_hash(client, db):
    from models import User

    signup(client, password="my-secret-pass")
    row = db.query(User).filter(User.email == "alice@example.com").one()
    assert row.password_hash != "my-secret-pass"
    assert row.password_hash.startswith("$argon2")


def test_duplicate_email_is_rejected_case_insensitively(client):
    assert signup(client, email="dup@example.com").status_code == 201
    assert signup(client, email="DUP@example.com").status_code == 409


def test_signup_validation(client):
    short = signup(client, password="pw-1234")  # 7 chars
    assert short.status_code == 422
    assert "pw-1234" not in short.text  # the submitted password is not echoed back
    assert signup(client, email="not-an-email").status_code == 422
    missing_name = client.post("/auth/signup", json={"email": "c@example.com", "password": "longenough1"})
    assert missing_name.status_code == 422


# ── login ──────────────────────────────────────────────────────────────────
def test_login_success(client):
    signup(client, email="a@example.com", password="correct-horse-1")
    resp = client.post("/auth/login", json={"email": "A@example.com", "password": "correct-horse-1"})
    assert resp.status_code == 200
    assert resp.json()["access_token"]
    assert resp.json()["user"]["email"] == "a@example.com"


def test_login_failures_share_one_generic_message(client):
    signup(client, email="a@example.com", password="correct-horse-1")
    wrong_pw = client.post("/auth/login", json={"email": "a@example.com", "password": "wrong-password"})
    unknown = client.post("/auth/login", json={"email": "nobody@example.com", "password": "wrong-password"})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json()["detail"] == unknown.json()["detail"] == GENERIC


def test_login_fails_for_legacy_user_without_password(client, db):
    from models import User

    db.add(User(email="legacy@example.com", username="legacy"))
    db.commit()
    resp = client.post("/auth/login", json={"email": "legacy@example.com", "password": "anything-at-all"})
    assert resp.status_code == 401 and resp.json()["detail"] == GENERIC


# ── /auth/me and token handling ────────────────────────────────────────────
def test_me_returns_current_user(client, make_user):
    user, headers = make_user()
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 200 and resp.json()["id"] == user["id"]


def test_me_rejects_missing_garbage_expired_and_orphan_tokens(client, make_user, db):
    from models import User

    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=auth_header("garbage")).status_code == 401

    secret = os.environ["JWT_SECRET"]
    user, headers = make_user()
    expired = jwt.encode(
        {"sub": str(user["id"]), "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        secret,
        algorithm="HS256",
    )
    assert client.get("/auth/me", headers=auth_header(expired)).status_code == 401

    wrong_secret = jwt.encode(
        {"sub": str(user["id"]), "exp": datetime.now(timezone.utc) + timedelta(days=1)},
        "a-different-secret-that-is-long-enough-123",
        algorithm="HS256",
    )
    assert client.get("/auth/me", headers=auth_header(wrong_secret)).status_code == 401

    db.query(User).filter(User.id == user["id"]).delete()
    db.commit()
    assert client.get("/auth/me", headers=headers).status_code == 401  # valid token, deleted user


def test_token_lifetime_is_seven_days(client):
    token = signup(client).json()["access_token"]
    claims = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
    assert abs((claims["exp"] - claims["iat"]) - 7 * 24 * 3600) < 5


def test_missing_jwt_secret_only_breaks_auth(client, make_user, monkeypatch):
    make_user("a@example.com", "A User", "correct-horse-1")
    monkeypatch.delenv("JWT_SECRET")
    ok_creds = {"email": "a@example.com", "password": "correct-horse-1"}
    assert client.post("/auth/login", json=ok_creds).status_code == 503
    assert client.get("/auth/me", headers=auth_header("anything")).status_code == 503
    assert client.get("/").status_code == 200  # the rest of the API still works


# ── rate limiting ──────────────────────────────────────────────────────────
def test_login_is_rate_limited(client):
    from auth import limiter

    limiter.enabled = True
    limiter.reset()
    try:
        codes = [
            client.post("/auth/login", json={"email": "x@example.com", "password": "wrong-password"}).status_code
            for _ in range(12)
        ]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes[:10] == [401] * 10
    assert 429 in codes[10:]


# ── protected legacy endpoints: isolation + 403 ────────────────────────────
def _add_attempt(db, user_id, question, topic="arrays"):
    from models import Attempt, TopicProgress

    db.add(Attempt(user_id=user_id, question=question, code="x", topic=topic, difficulty="easy"))
    db.add(TopicProgress(user_id=user_id, topic=topic, count=1, total_attempts=1))
    db.commit()


def test_user_data_endpoints_require_login(client):
    for path in ("/attempts/1", "/topic-stats/1", "/progress/1"):
        assert client.get(path).status_code == 401, path


def test_two_users_only_see_their_own_data(client, make_user, db):
    alice, alice_h = make_user("alice@example.com", "Alice A")
    bob, bob_h = make_user("bob@example.com", "Bob B")
    _add_attempt(db, alice["id"], "Alice question", topic="arrays")
    _add_attempt(db, bob["id"], "Bob question", topic="graphs")

    a = client.get(f"/attempts/{alice['id']}", headers=alice_h).json()
    b = client.get(f"/attempts/{bob['id']}", headers=bob_h).json()
    assert [x["question"] for x in a["attempts"]] == ["Alice question"]
    assert [x["question"] for x in b["attempts"]] == ["Bob question"]

    assert client.get(f"/topic-stats/{alice['id']}", headers=alice_h).json()["topics"] == {"arrays": 1}
    assert client.get(f"/topic-stats/{bob['id']}", headers=bob_h).json()["topics"] == {"graphs": 1}


def test_other_users_data_is_forbidden(client, make_user, db):
    alice, alice_h = make_user("alice@example.com", "Alice A")
    bob, _ = make_user("bob@example.com", "Bob B")
    _add_attempt(db, bob["id"], "Bob secret question")

    for path in (f"/attempts/{bob['id']}", f"/topic-stats/{bob['id']}", f"/progress/{bob['id']}"):
        resp = client.get(path, headers=alice_h)
        assert resp.status_code == 403, path
        assert "Bob secret" not in resp.text


def test_progress_works_for_own_user(client, make_user):
    user, headers = make_user()
    resp = client.get(f"/progress/{user['id']}", headers=headers)
    assert resp.status_code == 200 and resp.json()["user_id"] == user["id"]


# ── /analyze uses the token's identity, not the body's ─────────────────────
def _fake_groq():
    text = (
        "TIME_COMPLEXITY: O(n)\nSPACE_COMPLEXITY: O(1)\nBUGS: No bugs found\n"
        "BETTER_APPROACH: This is optimal\nSIMILAR_QUESTIONS: none\nINTERVIEWER_QUESTIONS: none"
    )
    create = lambda **kwargs: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_analyze_requires_login(client):
    resp = client.post("/analyze", json={"question": "Two Sum", "code": "pass"})
    assert resp.status_code == 401


def test_analyze_ignores_user_id_in_body(client, make_user, db, main_module, monkeypatch):
    from models import Attempt

    monkeypatch.setattr(main_module, "client", _fake_groq())
    alice, headers = make_user()
    resp = client.post(
        "/analyze",
        headers=headers,
        json={"question": "Two Sum", "code": "pass", "topic": "arrays", "user_id": 999},
    )
    assert resp.status_code == 200, resp.text
    attempts = db.query(Attempt).all()
    assert len(attempts) == 1 and attempts[0].user_id == alice["id"]


# ── demo user seed ─────────────────────────────────────────────────────────
def test_seed_demo_user_keeps_legacy_data_visible(client, db):
    from seed_demo_user import seed_demo_user

    _add_attempt(db, 1, "Legacy demo question")  # data that existed before auth
    assert seed_demo_user(db, "demo@example.com", "demo-password-1") == "created"

    token = client.post("/auth/login", json={"email": "demo@example.com", "password": "demo-password-1"}).json()["access_token"]
    resp = client.get("/attempts/1", headers=auth_header(token))
    assert resp.status_code == 200
    assert [a["question"] for a in resp.json()["attempts"]] == ["Legacy demo question"]


def test_seed_demo_user_is_idempotent_and_keeps_password(db):
    from auth import verify_password
    from models import User
    from seed_demo_user import seed_demo_user

    assert seed_demo_user(db, "demo@example.com", "first-password") == "created"
    assert seed_demo_user(db, "demo@example.com", "other-password") == "unchanged"
    assert verify_password("first-password", db.get(User, 1).password_hash)
    assert seed_demo_user(db, "demo@example.com", "other-password", reset_password=True) == "updated"
    assert verify_password("other-password", db.get(User, 1).password_hash)


def test_seed_demo_user_rejects_email_used_by_someone_else(client, db):
    import pytest
    from seed_demo_user import seed_demo_user

    signup(client, email="filler@example.com")  # becomes id=1
    signup(client, email="taken@example.com")   # id=2
    with pytest.raises(ValueError):
        seed_demo_user(db, "taken@example.com", "demo-password-1")
