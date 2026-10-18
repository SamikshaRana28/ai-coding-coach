"""API tests for the Problems feature (SQLite in memory, LLM faked). Run: pytest tests/ -v"""
from tests.conftest import SEED_ROWS

CODE = "def two_sum(nums, target):\n    return []"
# USER2 = {"X-User-Id": "2"}


def ids_by_slug(api):
    items = api.client.get("/problems", params={"page_size": 100}).json()["items"]
    return {p["slug"]: p["id"] for p in items}


def submit(api, problem_id, code=CODE, language="python", headers=None):
    return api.client.post(f"/problems/{problem_id}/submit",
                           json={"code": code, "language": language}, headers=headers or {})


def topic_stats(api, user_id=1):
    return api.client.get(f"/topic-stats/{user_id}").json()


# ── seed ──────────────────────────────────────────────────────────────────────
def test_seed_is_idempotent(api):
    from models import Problem
    from scripts.seed_problems import seed

    db = api.Session()
    again = seed(db, [dict(r) for r in SEED_ROWS])
    assert again == {"inserted": 0, "updated": 0, "unchanged": 6, "skipped_custom": 0}
    assert db.query(Problem).count() == 6

    # a changed row is repaired in place, still no duplicates
    p = db.query(Problem).filter(Problem.slug == "two-sum").first()
    p.description = "tampered"
    db.commit()
    third = seed(db, [dict(r) for r in SEED_ROWS])
    assert third["updated"] == 1 and third["inserted"] == 0
    assert db.query(Problem).count() == 6
    assert db.query(Problem).filter(Problem.slug == "two-sum").first().description == SEED_ROWS[0]["description"]
    db.close()


def test_seed_never_overwrites_custom_problems(api):
    from models import Problem
    from scripts.seed_problems import seed

    db = api.Session()
    p = db.query(Problem).filter(Problem.slug == "two-sum").first()
    p.source, p.description = "custom", "my own version"
    db.commit()
    stats = seed(db, [dict(r) for r in SEED_ROWS])
    assert stats["skipped_custom"] == 1
    assert db.query(Problem).filter(Problem.slug == "two-sum").first().description == "my own version"
    db.close()


# ── list / filters / pagination ───────────────────────────────────────────────
def test_list_pagination(api):
    r1 = api.client.get("/problems", params={"page": 1, "page_size": 4}).json()
    assert r1["total"] == 6 and r1["total_pages"] == 2 and len(r1["items"]) == 4
    r2 = api.client.get("/problems", params={"page": 2, "page_size": 4}).json()
    assert len(r2["items"]) == 2
    ids = [p["id"] for p in r1["items"] + r2["items"]]
    assert ids == sorted(ids) and len(set(ids)) == 6
    assert api.client.get("/problems", params={"page": 99, "page_size": 4}).json()["items"] == []
    assert api.client.get("/problems", params={"page_size": 1000}).status_code == 422


def test_list_items_are_light_and_complete(api):
    item = api.client.get("/problems").json()["items"][0]
    assert {"id", "title", "slug", "difficulty", "topics", "acceptance_rate", "source",
            "url", "status", "attempts_count"} <= set(item)
    assert "description" not in item and "last_code" not in item
    assert item["status"] == "todo" and item["source"] == "leetcode"


def test_list_filters(api):
    get = lambda **p: api.client.get("/problems", params=p).json()
    assert get(difficulty="Easy")["total"] == 2
    assert get(difficulty="easy")["total"] == 2                 # case-insensitive
    assert get(difficulty="Hard")["items"][0]["title"] == "Merge k Sorted Lists"
    assert get(topic="dp")["total"] == 1
    assert get(topic="strings")["items"][0]["slug"] == "longest-palindromic-substring"
    assert get(topic="trees")["total"] == 1
    assert get(search="two")["total"] == 2                      # Two Sum, Add Two Numbers
    assert get(search="TWO SUM")["total"] == 1                  # case-insensitive
    assert get(search="%")["total"] == 0                        # wildcards are escaped, not interpreted
    assert get(search="_")["total"] == 0
    assert get(difficulty="Medium", topic="graphs")["total"] == 1
    assert get(difficulty="Easy", topic="graphs")["total"] == 0
    assert get(difficulty="", topic="", search="", status="")["total"] == 6   # blanks mean "no filter"


def test_list_rejects_bad_filter_values(api):
    assert api.client.get("/problems", params={"difficulty": "insane"}).status_code == 422
    assert api.client.get("/problems", params={"status": "done"}).status_code == 422


def test_status_is_per_user_and_filterable(api):
    pid = ids_by_slug(api)["two-sum"]
    assert submit(api, pid).status_code == 200                # user 1 solves it

    mine = api.client.get("/problems", params={"status": "solved"}).json()
    assert mine["total"] == 1 and mine["items"][0]["id"] == pid
    assert api.client.get("/problems", params={"status": "todo"}).json()["total"] == 5

    theirs = api.client.get("/problems", params={"status": "solved"}, headers=api.h2).json()
    assert theirs["total"] == 0
    other = [p for p in api.client.get("/problems", headers=api.h2).json()["items"] if p["id"] == pid][0]
    assert other["status"] == "todo"


def test_problems_require_login_and_ignore_x_user_id(api):
    from fastapi.testclient import TestClient

    anon = TestClient(api.main.app)                       # no Authorization header
    assert anon.get("/problems").status_code == 401
    assert anon.get("/problems", headers={"X-User-Id": "1"}).status_code == 401   # header is NOT identity
    assert anon.get("/problems/1").status_code == 401
    assert anon.post("/problems/1/submit", json={"code": "x"}).status_code == 401
    assert anon.post("/problems/1/mark-solved").status_code == 401

    # a spoofed header cannot make user 1 act as user 2
    pid = ids_by_slug(api)["two-sum"]
    submit(api, pid)                                      # user 1 solves it
    spoofed = api.client.get("/problems", params={"status": "solved"}, headers={"X-User-Id": "2"}).json()
    assert spoofed["total"] == 1                          # still user 1's data


# ── detail ────────────────────────────────────────────────────────────────────
def test_detail_includes_user_state(api):
    pid = ids_by_slug(api)["two-sum"]
    d = api.client.get(f"/problems/{pid}").json()
    assert d["description"] == SEED_ROWS[0]["description"]
    assert d["status"] == "todo" and d["last_code"] is None and d["hints_used"] == 0

    submit(api, pid, code="print('mine')")
    d = api.client.get(f"/problems/{pid}").json()
    assert d["last_code"] == "print('mine')" and d["status"] == "solved" and d["solved_at"]
    # another user still sees a clean slate
    assert api.client.get(f"/problems/{pid}", headers=api.h2).json()["last_code"] is None


def test_detail_404(api):
    assert api.client.get("/problems/99999").status_code == 404
    assert submit(api, 99999).status_code == 404
    assert api.client.post("/problems/99999/mark-solved").status_code == 404


# ── submit ────────────────────────────────────────────────────────────────────
def test_submit_clean_solves_and_updates_legacy_tables(api):
    pid = ids_by_slug(api)["two-sum"]
    res = submit(api, pid)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "solved" and body["newly_solved"] is True and body["attempts_count"] == 1
    assert body["clean"] is True
    assert set(body["review"]) == {"time_complexity", "space_complexity", "bugs", "better_approach",
                                   "similar_questions", "interviewer_questions"}

    # the LLM got the problem title as the question and the statement as extra context
    call = api.llm.calls[-1]
    assert call["question"] == "Two Sum" and call["statement"] == SEED_ROWS[0]["description"]

    # old pages stay consistent: Topic Tracker, attempts history
    stats = topic_stats(api)
    assert stats["topics"] == {"arrays": 1} and stats["total_attempts"] == 1 and stats["acceptance_rate"] == 1.0
    attempts = api.client.get("/attempts/1").json()
    assert attempts["total"] == 1
    assert attempts["attempts"][0]["question"] == "Two Sum"
    assert attempts["attempts"][0]["topic"] == "arrays" and attempts["attempts"][0]["difficulty"] == "easy"


def test_submit_with_bugs_is_attempted_then_resubmit_solves(api):
    pid = ids_by_slug(api)["two-sum"]
    api.llm.bugs = "Line 2: returns empty list when a pair exists"
    body = submit(api, pid).json()
    assert body["status"] == "attempted" and body["newly_solved"] is False and body["attempts_count"] == 1
    assert body["clean"] is False
    assert topic_stats(api)["topics"] == {"arrays": 0}          # attempted, not solved

    api.llm.bugs = "No bugs found"
    body = submit(api, pid).json()
    assert body["status"] == "solved" and body["newly_solved"] is True and body["attempts_count"] == 2
    stats = topic_stats(api)
    assert stats["topics"] == {"arrays": 1} and stats["total_attempts"] == 2 and stats["acceptance_rate"] == 0.5


def test_solved_never_downgrades_and_counts_once(api):
    pid = ids_by_slug(api)["two-sum"]
    assert submit(api, pid).json()["newly_solved"] is True

    api.llm.bugs = "A new bug appears"
    assert submit(api, pid).json()["status"] == "solved"        # still solved

    api.llm.bugs = "No bugs found."                             # trailing period must still count as clean
    body = submit(api, pid).json()
    assert body["status"] == "solved" and body["newly_solved"] is False and body["attempts_count"] == 3
    assert body["clean"] is True
    stats = topic_stats(api)
    assert stats["topics"] == {"arrays": 1}                     # one problem = one solve
    assert stats["total_attempts"] == 3


def test_submit_uses_primary_topic(api):
    pid = ids_by_slug(api)["longest-palindromic-substring"]      # topics ["dp", "strings"]
    submit(api, pid)
    assert topic_stats(api)["topics"] == {"dp": 1}


def test_submit_validation(api):
    pid = ids_by_slug(api)["two-sum"]
    assert api.client.post(f"/problems/{pid}/submit", json={"code": "", "language": "python"}).status_code == 422
    assert api.client.post(f"/problems/{pid}/submit", json={"code": "   \n", "language": "python"}).status_code == 422
    assert api.client.post(f"/problems/{pid}/submit", json={"code": "x", "language": "cobol"}).status_code == 422
    assert api.client.post(f"/problems/{pid}/submit", json={"language": "python"}).status_code == 422
    assert api.llm.calls == []                                   # nothing reached the LLM


def test_submit_ai_failure_writes_nothing(api):
    from fastapi import HTTPException
    pid = ids_by_slug(api)["two-sum"]
    api.llm.error = HTTPException(status_code=503, detail="GROQ_API_KEY missing")
    res = submit(api, pid)
    assert res.status_code == 503
    d = api.client.get(f"/problems/{pid}").json()
    assert d["status"] == "todo" and d["attempts_count"] == 0 and d["last_code"] is None
    assert api.client.get("/attempts/1").json()["total"] == 0
    assert topic_stats(api)["topics"] == {}


# ── mark-solved ───────────────────────────────────────────────────────────────
def test_mark_solved_is_idempotent_and_counts_in_topic_tracker(api):
    pid = ids_by_slug(api)["number-of-islands"]
    first = api.client.post(f"/problems/{pid}/mark-solved").json()
    assert first["status"] == "solved" and first["newly_solved"] is True and first["solved_at"]
    assert topic_stats(api)["topics"] == {"graphs": 1}

    second = api.client.post(f"/problems/{pid}/mark-solved").json()
    assert second["status"] == "solved" and second["newly_solved"] is False
    stats = topic_stats(api)
    assert stats["topics"] == {"graphs": 1} and stats["acceptance_rate"] <= 1.0
    assert api.client.get("/attempts/1").json()["total"] == 1


def test_mark_solved_after_failed_attempt(api):
    pid = ids_by_slug(api)["two-sum"]
    api.llm.bugs = "bug"
    submit(api, pid)
    assert api.client.get(f"/problems/{pid}").json()["status"] == "attempted"
    assert api.client.post(f"/problems/{pid}/mark-solved").json()["status"] == "solved"
    d = api.client.get(f"/problems/{pid}").json()
    assert d["status"] == "solved" and d["attempts_count"] == 1   # attempts_count only counts submissions


# ── other pages ───────────────────────────────────────────────────────────────
def test_progress_page_reflects_a_real_submission(api):
    # no data yet -> demo curve (8 weeks)
    assert api.client.get("/progress/1").json()["weeks"] == 8
    submit(api, ids_by_slug(api)["two-sum"])
    after = api.client.get("/progress/1").json()
    assert after["weeks"] == 1
    assert after["progress"][0]["arrays"] == 1


def test_analyze_endpoint_still_works_and_records(api):
    payload = {"question": "Two Sum", "code": CODE, "language": "python",
               "topic": "arrays", "difficulty": "easy", "user_id": 1}
    res = api.client.post("/analyze", json=payload)
    assert res.status_code == 200 and res.json()["bugs"] == "No bugs found"
    assert topic_stats(api)["topics"] == {"arrays": 1}
    assert api.client.get("/attempts/1").json()["total"] == 1

    # /analyze keeps its old semantics: every clean analysis counts (it has no per-problem identity)
    api.client.post("/analyze", json=payload)
    assert topic_stats(api)["topics"] == {"arrays": 2}


def test_recommend_adds_problem_id(api, monkeypatch):
    similar = [
        {"title": "Two Sum", "difficulty": "Easy", "topics": "Array,Hash Table", "similarity_score": 0.9},
        {"title": "Not In Bank", "difficulty": "Hard", "topics": "Math", "similarity_score": 0.5},
    ]
    monkeypatch.setattr(api.main, "get_similar_questions", lambda title, top_n=3: similar)
    res = api.client.post("/recommend", json={"title": "3Sum"}).json()["similar_questions"]
    assert res[0]["problem_id"] == ids_by_slug(api)["two-sum"]
    assert res[1]["problem_id"] is None
    assert res[0]["title"] == "Two Sum" and res[0]["similarity_score"] == 0.9   # old fields intact


# ── admin: add a custom problem ───────────────────────────────────────────────
NEW = {"title": "Reverse Words", "difficulty": "easy", "topics": ["Dynamic Programming", "string"],
       "description": "Reverse the words in a sentence."}


def test_admin_endpoint_disabled_without_token_env(api, monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)   # a dev .env may define it
    res = api.client.post("/admin/problems", json=NEW, headers={"X-Admin-Token": "anything"})
    assert res.status_code == 503


def test_admin_endpoint_flow(api, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "s3cret")
    assert api.client.post("/admin/problems", json=NEW).status_code == 403
    assert api.client.post("/admin/problems", json=NEW, headers={"X-Admin-Token": "nope"}).status_code == 403

    ok = api.client.post("/admin/problems", json=NEW, headers={"X-Admin-Token": "s3cret"})
    assert ok.status_code == 201
    body = ok.json()
    assert body["source"] == "custom" and body["difficulty"] == "Easy"
    assert body["topics"] == ["dp", "strings"] and body["slug"] == "reverse-words"

    # it shows up in the normal list and can be submitted to like any other problem
    custom = api.client.get("/problems", params={"search": "reverse"}).json()["items"]
    assert [p["source"] for p in custom] == ["custom"]
    assert submit(api, body["id"]).status_code == 200
    assert topic_stats(api)["topics"] == {"dp": 1}

    h = {"X-Admin-Token": "s3cret"}
    assert api.client.post("/admin/problems", json=NEW, headers=h).status_code == 409          # duplicate
    assert api.client.post("/admin/problems", json={**NEW, "title": "X", "difficulty": "insane"},
                           headers=h).status_code == 422
    assert api.client.post("/admin/problems", json={**NEW, "title": "Y", "description": ""},
                           headers=h).status_code == 422
