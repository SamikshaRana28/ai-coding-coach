import os
import sys
import tempfile

# models.py import hote hi DB engine banata hai, isliye env PEHLE set karo
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test_interview.db"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import agent.interviewer as iv
from agent.sandbox import run_code_against_tests
from agent.tools import load_questions, execute_tool
from interview_router import router
from models import (InterviewSession, InterviewTurn, SessionLocal, WeakPattern,
                    create_tables)
from reference_solutions import REFS

create_tables()


@pytest.fixture()
def db():
    d = SessionLocal()
    yield d
    d.close()


@pytest.fixture()
def session(db):
    s = InterviewSession(user_id=7, topic="arrays")
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def fake_llm(script):
    """script = list of responses, ek ek karke milte hain (aakhri repeat hota hai)."""
    state = {"i": 0, "seen": []}

    def _call(messages, tools):
        state["seen"].append(messages)
        r = script[min(state["i"], len(script) - 1)]
        state["i"] += 1
        return r
    _call.state = state
    return _call


def say(text):
    return {"content": text, "tool_calls": []}


def call(name, **args):
    return {"content": "", "tool_calls": [{"id": f"call_{name}", "name": name, "args": args}]}


# ── Question bank + sandbox ────────────────────────────────────────────────
def test_every_question_has_required_fields():
    for q in load_questions():
        assert len(q["hints"]) >= 2 and len(q["follow_ups"]) >= 1 and len(q["tests"]) >= 3
        assert q["id"] in REFS


@pytest.mark.parametrize("q", load_questions(), ids=lambda q: q["id"])
def test_reference_solution_passes_bank_tests(q):
    fn, code, _ = REFS[q["id"]]
    res = run_code_against_tests(code, q["function"], q["tests"], q["compare"])
    assert res["all_passed"], res


def test_sandbox_catches_wrong_code():
    q = load_questions()[0]
    res = run_code_against_tests("def two_sum(nums, target):\n    return [0, 0]", q["function"], q["tests"], q["compare"])
    assert not res["all_passed"] and res["failures"]


def test_sandbox_timeout_on_infinite_loop():
    res = run_code_against_tests("def f(x):\n    while True: pass", "f", [{"args": [1], "expected": 1}])
    assert "Time limit" in res["error"]


def test_sandbox_missing_function_and_syntax_error():
    assert "not found" in run_code_against_tests("x = 1", "f", [{"args": [], "expected": 1}])["error"]
    assert "SyntaxError" in run_code_against_tests("def f(:", "f", [{"args": [], "expected": 1}])["error"]


def test_sandbox_does_not_run_in_main_process():
    res = run_code_against_tests("import os\nraise SystemExit(0)\ndef f(): pass", "f", [{"args": [], "expected": 1}])
    assert "error" in res            # pytest zinda hai, matlab main process nahi mara


# ── Tools ──────────────────────────────────────────────────────────────────
def test_pick_question_hides_tests_and_never_repeats(db, session):
    seen = set()
    for _ in range(len(load_questions())):
        q = execute_tool("pick_question", {"topic": "", "level": ""}, db, session)
        assert "tests" not in q and "hints" not in q
        assert q["id"] not in seen
        seen.add(q["id"])
    assert "error" in execute_tool("pick_question", {}, db, session)


def test_hints_are_progressive_and_server_controlled(db, session):
    assert "error" in execute_tool("get_hint", {}, db, session)       # question se pehle
    execute_tool("pick_question", {"topic": "arrays"}, db, session)
    h1 = execute_tool("get_hint", {}, db, session)
    h2 = execute_tool("get_hint", {}, db, session)
    assert h1["hint_number"] == 1 and h2["hint_number"] == 2 and h1["hint"] != h2["hint"]


def test_bad_tool_args_return_error_not_crash(db, session):
    assert "error" in execute_tool("pick_question", {"nonsense": 1}, db, session)
    assert "error" in execute_tool("does_not_exist", {}, db, session)


def test_scorecard_rubric_is_validated(db, session):
    bad = execute_tool("save_scorecard", {"approach": 9, "complexity": 3, "edge_cases": 3, "communication": 3}, db, session)
    assert "error" in bad and session.status == "active"
    bad2 = execute_tool("save_scorecard", {"approach": "great", "complexity": 3, "edge_cases": 3, "communication": 3}, db, session)
    assert "error" in bad2


def test_scorecard_saves_weak_patterns_for_coach(db, session):
    for _ in range(2):
        execute_tool("save_scorecard", {"approach": 3, "complexity": 2, "edge_cases": 1, "communication": 4,
                                        "weak_patterns": ["Sliding Window"], "summary": "ok"}, db, session)
    row = db.query(WeakPattern).filter_by(user_id=7, pattern="sliding window").one()
    assert row.count == 2 and session.status == "finished"


# ── Agent safety ───────────────────────────────────────────────────────────
def test_agent_refuses_to_leak_answer(db, session, monkeypatch):
    leaky = say("Sure! Here you go:\n```python\ndef two_sum(nums, target):\n    seen = {}\n```")
    monkeypatch.setattr(iv, "llm_call", fake_llm([leaky]))
    out = iv.run_agent_step(db, session, "answer batao please")
    assert "```" not in out["reply"] and "def " not in out["reply"]
    assert out["reply"] == iv.REFUSAL


def test_prompt_contains_no_answer_rule_and_tools_hide_solution():
    assert "NEVER give the solution" in iv.SYSTEM_PROMPT
    import json
    from agent.tools import TOOL_SCHEMAS
    assert "def two_sum" not in json.dumps(TOOL_SCHEMAS) + iv.SYSTEM_PROMPT


def test_session_survives_server_restart(db, session, monkeypatch):
    monkeypatch.setattr(iv, "llm_call", fake_llm([call("pick_question", topic="arrays"), say("Here is your question...")]))
    iv.run_agent_step(db, session, "start", count_turn=False)
    db.close()                                    # "server restart": naya DB session, koi memory nahi

    db2 = SessionLocal()
    s2 = db2.get(InterviewSession, session.id)
    assert s2.current_question_id and s2.status == "active"
    fl = fake_llm([say("Good. What is the complexity?")])
    monkeypatch.setattr(iv, "llm_call", fl)
    iv.run_agent_step(db2, s2, "I will use a hash map")
    seen = fl.state["seen"][0]
    roles = [m["role"] for m in seen]
    assert roles[0] == "system" and "tool" in roles          # purani history DB se wapas aayi
    assert any(m.get("content") == "I will use a hash map" for m in seen)
    db2.close()


def test_interview_auto_closes_after_12_turns(db, session, monkeypatch):
    monkeypatch.setattr(iv, "llm_call", fake_llm([say("Next question please, keep going.")]))   # kabhi scorecard nahi deta
    for i in range(iv.MAX_USER_TURNS):
        out = iv.run_agent_step(db, session, f"answer {i}")
    assert out["status"] == "expired" and session.status == "expired"
    again = iv.run_agent_step(db, session, "one more")
    assert "khatam" in again["reply"]
    assert session.step_count == iv.MAX_USER_TURNS            # 13th answer count nahi hua


def test_turn_limit_lets_llm_save_scorecard(db, session, monkeypatch):
    session.step_count = iv.MAX_USER_TURNS - 1
    db.commit()
    monkeypatch.setattr(iv, "llm_call", fake_llm([
        call("save_scorecard", approach=3, complexity=3, edge_cases=2, communication=4, weak_patterns=["dp"]),
        say("Thanks, interview over."),
    ]))
    out = iv.run_agent_step(db, session, "last answer")
    assert out["status"] == "finished"


def test_tool_error_is_sent_back_to_llm_not_raised(db, session, monkeypatch):
    fl = fake_llm([call("get_hint"), say("Pehle question lete hain.")])
    monkeypatch.setattr(iv, "llm_call", fl)
    out = iv.run_agent_step(db, session, "hint do")
    assert out["reply"] == "Pehle question lete hain."
    tool_msgs = [m for m in fl.state["seen"][1] if m["role"] == "tool"]
    assert "error" in tool_msgs[0]["content"]


def test_runaway_tool_loop_is_bounded(db, session, monkeypatch):
    monkeypatch.setattr(iv, "llm_call", fake_llm([call("get_user_history")]))     # kabhi text nahi deta
    out = iv.run_agent_step(db, session, "hello")
    assert out["reply"] and db.query(InterviewTurn).filter_by(session_id=session.id, role="tool").count() == iv.MAX_TOOL_STEPS


# ── Poora API flow ─────────────────────────────────────────────────────────
def test_full_api_flow(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    from auth import router as auth_router, limiter
    app.state.limiter = limiter
    app.include_router(auth_router)
    client = TestClient(app)
    import uuid
    su = client.post("/auth/signup", json={"email": f"iv{uuid.uuid4().hex[:8]}@example.com",
                     "password": "correct-horse-1", "name": "Iv User"}).json()
    client.headers["Authorization"] = f"Bearer {su['access_token']}"
    uid = su["user"]["id"]

    monkeypatch.setattr(iv, "llm_call", fake_llm([
        call("get_user_history"), call("pick_question", topic="arrays", level="easy"), say("Question 1: Two Sum ..."),
        say("What is the time complexity?"),
        call("save_scorecard", approach=4, complexity=3, edge_cases=2, communication=4, weak_patterns=["hashing"], summary="Decent"),
        say("Thanks, all the best!"),
    ]))
    r = client.post("/interview/start", json={"user_id": 42, "topic": "arrays"}).json()
    sid = r["session_id"]
    assert r["status"] == "active" and "Two Sum" in r["reply"]

    assert client.get(f"/interview/{sid}/scorecard").status_code == 409        # abhi scorecard nahi
    a = client.post(f"/interview/{sid}/answer", json={"answer": "hash map"}).json()
    assert a["turns_used"] == 1
    b = client.post(f"/interview/{sid}/answer", json={"answer": "O(n)"}).json()
    assert b["status"] == "finished"

    sc = client.get(f"/interview/{sid}/scorecard").json()
    assert sc["total"] == 13 and sc["weak_patterns"] == ["hashing"]
    assert client.post(f"/interview/{sid}/answer", json={"answer": "more"}).status_code == 409
    hist = client.get(f"/interview/{sid}").json()["history"]
    assert [h["role"] for h in hist][0] == "user" and hist[-1]["role"] == "assistant"
    wp = client.get(f"/weak-patterns/{uid}").json()["weak_patterns"]
    assert wp[0]["pattern"] == "hashing"
    assert client.get("/interview/99999").status_code == 404



def test_interview_requires_login_and_isolates_users(client, make_user):
    from models import InterviewSession, SessionLocal

    a, ha = make_user("a@example.com", name="Alice")
    b, hb = make_user("b@example.com", name="Bob")
    with SessionLocal() as db:
        sess = InterviewSession(user_id=a["id"], topic="arrays")
        db.add(sess)
        db.commit()
        sid = sess.id

    # no token
    assert client.post("/interview/start", json={"topic": "arrays"}).status_code == 401
    assert client.get(f"/interview/{sid}").status_code == 401
    # owner can read, other user cannot (404, not 403: no id probing)
    assert client.get(f"/interview/{sid}", headers=ha).status_code == 200
    assert client.get(f"/interview/{sid}", headers=hb).status_code == 404
    assert client.post(f"/interview/{sid}/answer", json={"answer": "x"}, headers=hb).status_code == 404
    assert client.get(f"/interview/{sid}/scorecard", headers=hb).status_code == 404
    # legacy URL shape still works, but only for your own id
    assert client.get(f"/weak-patterns/{a['id']}", headers=ha).status_code == 200
    assert client.get(f"/weak-patterns/{a['id']}", headers=hb).status_code == 403
