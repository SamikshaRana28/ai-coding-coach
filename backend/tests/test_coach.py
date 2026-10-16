"""
Tests for the Coach agent (Part 3): tools, the agent loop, and the /coach endpoints.

Safe to run against any DB: it never drops tables, it only creates/deletes rows
for the fake users below (and problems whose slug starts with "coachtest-").
The Groq client is always a fake - no network, no API key needed.
"""
import json
import os
import sys
import tempfile
import time
import types
from types import SimpleNamespace

# If nothing configured a DB yet (plain `pytest` run), use a throwaway SQLite file.
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/coach_test.db")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import coach_router
from agent import coach as coach_mod
from agent.coach import MAX_STEPS, run_coach
from agent.coach_tools import MAX_TOOL_OUTPUT_CHARS, ToolContext, execute_tool, tool_schemas
from models import (
    Attempt, Base, CoachMessage, Problem, SessionLocal, TopicProgress, UserProblem, engine,
)

U1, U2 = 900001, 900002          # fake users (A and B)


# ── fixtures ────────────────────────────────────────────────────────────────
def _cleanup(db):
    db.rollback()
    for model in (CoachMessage, UserProblem, Attempt, TopicProgress):
        db.query(model).filter(model.user_id.in_([U1, U2])).delete(synchronize_session=False)
    db.query(Problem).filter(Problem.slug.like("coachtest-%")).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def db():
    Base.metadata.create_all(engine)      # non-destructive
    session = SessionLocal()
    _cleanup(session)
    yield session
    _cleanup(session)
    session.close()


def _problem(db, title, difficulty="Easy", topics=("arrays",), description="Do the thing."):
    p = Problem(title=title, slug="coachtest-" + title.lower().replace(" ", "-"), difficulty=difficulty,
                topics=list(topics), description=description, source="test")
    db.add(p)
    db.commit()
    return p


def _progress(db, user_id, topic, solved, attempts):
    db.add(TopicProgress(user_id=user_id, topic=topic, count=solved, total_attempts=attempts))
    db.commit()


# ── scripted fake Groq client ───────────────────────────────────────────────
def tool_call(name, arguments=None, call_id="call_1"):
    args = arguments if isinstance(arguments, str) else json.dumps(arguments or {})
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=args))


def reply_tools(*calls, content=""):
    return SimpleNamespace(content=content, tool_calls=list(calls))


def reply_text(text):
    return SimpleNamespace(content=text, tool_calls=None)


class FakeClient:
    """Returns the scripted replies in order (repeats the last one forever). Records every call."""

    def __init__(self, *script):
        self.script = list(script)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        msg = self.script[min(len(self.calls) - 1, len(self.script) - 1)]
        if isinstance(msg, Exception):
            raise msg
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def tool_messages(client_call):
    return [m for m in client_call["messages"] if m["role"] == "tool"]


# ═══ 1. tools ═══════════════════════════════════════════════════════════════
def run_tool(db, user_id, name, args=None):
    ok, text = execute_tool(name, json.dumps(args or {}), ToolContext(db=db, user_id=user_id))
    return ok, json.loads(text)


def test_get_topic_stats_only_returns_this_users_data(db):
    _progress(db, U1, "arrays", 4, 8)
    _progress(db, U1, "dp", 1, 2)
    _progress(db, U2, "graphs", 9, 9)
    ok, out = run_tool(db, U1, "get_topic_stats")
    assert ok and out["topics_solved"] == {"arrays": 4, "dp": 1}
    assert out["acceptance_rate"] == 0.5 and out["total_attempts"] == 10 and out["low_data"] is True
    _, other = run_tool(db, U2, "get_topic_stats")
    assert other["topics_solved"] == {"graphs": 9}


def test_get_attempts_limit_topic_and_isolation(db):
    for i in range(3):
        db.add(Attempt(user_id=U1, question=f"Q{i}", code="secret code", topic="arrays", difficulty="easy",
                       time_complexity="O(n)", space_complexity="O(1)", bugs_found=i % 2))
    db.add(Attempt(user_id=U1, question="Graph Q", code="x", topic="graphs", difficulty="hard", bugs_found=0))
    db.add(Attempt(user_id=U2, question="Other user's Q", code="x", topic="arrays", difficulty="easy", bugs_found=0))
    db.commit()

    _, out = run_tool(db, U1, "get_attempts", {"limit": 2})
    assert out["count"] == 2
    assert "code" not in out["attempts"][0]                       # code is not sent to the model
    _, out = run_tool(db, U1, "get_attempts", {"topic": "ARRAYS", "limit": 10})
    assert out["count"] == 3 and all(a["topic"] == "arrays" for a in out["attempts"])
    assert "Other user's Q" not in json.dumps(out)


def test_readiness_score_uses_real_numbers(db):
    _progress(db, U1, "arrays", 6, 10)
    _progress(db, U1, "dp", 2, 5)
    from ml.score import calculate_readiness_score

    ok, out = run_tool(db, U1, "get_readiness_score")
    expected = calculate_readiness_score(6, 0, 2, 0, 0, 0, 15 / 8, 8 / 15)
    assert ok and out["total_score"] == expected["total_score"]
    assert out["inputs"]["arrays_solved"] == 6 and out["inputs"]["dp_solved"] == 2
    assert out["total_attempts"] == 15 and out["low_data"] is False


def test_predict_weak_topic_adds_plain_stats_and_uncertainty(db):
    _progress(db, U1, "arrays", 5, 7)
    ok, out = run_tool(db, U1, "predict_weak_topic")
    assert ok
    assert out["model_prediction"]["weak_topic"] in ("arrays", "dp", "graphs", "math", "strings", "trees")
    assert out["low_data"] is True and "synthetic" in out["reliability_note"]
    assert out["plain_stats"]["solved_per_topic"]["arrays"] == 5
    assert "arrays" not in out["plain_stats"]["fewest_solved"]


def test_predict_weak_topic_with_no_attempts_skips_the_model(db):
    ok, out = run_tool(db, U1, "predict_weak_topic")
    assert ok and out["model_prediction"] is None and out["total_attempts"] == 0


def test_get_similar_questions_wraps_recommender(db, monkeypatch):
    fake = types.ModuleType("ml.recommender")
    seen = {}

    def fake_similar(title, top_n=3):
        seen.update(title=title, top_n=top_n)
        return [{"title": "3Sum", "difficulty": "Medium", "topics": "Array", "similarity_score": 0.8}]

    fake.get_similar_questions = fake_similar
    monkeypatch.setitem(sys.modules, "ml.recommender", fake)
    ok, out = run_tool(db, U1, "get_similar_questions", {"title": "Two Sum", "limit": 2})
    assert ok and out["similar"][0]["title"] == "3Sum" and seen == {"title": "Two Sum", "top_n": 2}


def test_predict_difficulty_wraps_classifier(db):
    ok, out = run_tool(db, U1, "predict_difficulty", {"title": "Two Sum", "description": "find two numbers"})
    assert ok and out["predicted_difficulty"] in ("Easy", "Medium", "Hard")
    assert 0 <= out["confidence"] <= 1


def test_search_problems_filters_and_per_user_status(db):
    a = _problem(db, "Alpha Arrays", "Easy", ["arrays"])
    b = _problem(db, "Beta DP", "Hard", ["dp"])
    _problem(db, "Gamma Graphs", "Easy", ["graphs", "strings"])
    db.add(UserProblem(user_id=U1, problem_id=a.id, status="solved", attempts_count=1))
    db.add(UserProblem(user_id=U2, problem_id=b.id, status="attempted", attempts_count=2))
    db.commit()

    def titles(user, **args):
        _, out = run_tool(db, user, "search_problems", {"limit": 10, **args})
        return [p["title"] for p in out["problems"] if p["title"].split()[0] in ("Alpha", "Beta", "Gamma")]

    assert titles(U1, topic="graphs") == ["Gamma Graphs"]
    assert titles(U1, difficulty="hard") == ["Beta DP"]
    assert titles(U1, status="solved") == ["Alpha Arrays"]
    assert titles(U2, status="solved") == []
    assert titles(U2, status="attempted") == ["Beta DP"]
    assert titles(U1, status="attempted") == []                       # U2's attempt is invisible to U1
    assert "Beta DP" in titles(U1, status="todo")
    ok, out = run_tool(db, U1, "search_problems", {"topic": "nonsense"})
    assert not ok and "topic must be one of" in out["error"]


def test_get_problem_includes_only_own_status_and_code(db):
    p = _problem(db, "Delta Problem", description="x" * 5000)
    db.add(UserProblem(user_id=U1, problem_id=p.id, status="attempted", attempts_count=3, last_code="my code"))
    db.add(UserProblem(user_id=U2, problem_id=p.id, status="solved", attempts_count=1, last_code="THEIR CODE"))
    db.commit()
    _, mine = run_tool(db, U1, "get_problem", {"problem_id": p.id})
    assert mine["your_status"] == "attempted" and mine["your_attempts"] == 3
    assert mine["your_last_code"] == "my code" and len(mine["description"]) == 1500
    assert "THEIR CODE" not in json.dumps(mine)
    _, theirs = run_tool(db, U2, "get_problem", {"problem_id": p.id})
    assert theirs["your_status"] == "solved"
    ok, missing = run_tool(db, U1, "get_problem", {"problem_id": 99999999})
    assert not ok and "No problem" in missing["error"]


# ── tool plumbing: validation, errors, injection, truncation ────────────────
def test_user_id_is_not_in_any_tool_schema():
    assert "user_id" not in json.dumps(tool_schemas())
    assert {s["function"]["name"] for s in tool_schemas()} >= {
        "get_topic_stats", "get_attempts", "get_readiness_score", "predict_weak_topic",
        "get_similar_questions", "predict_difficulty", "search_problems", "get_problem",
    }


def test_model_cannot_pass_a_user_id(db):
    _progress(db, U2, "graphs", 9, 9)
    ok, out = run_tool(db, U1, "get_topic_stats", {"user_id": U2})
    assert not ok and "error" in out and "graphs" not in json.dumps(out)
    ok, out = run_tool(db, U1, "get_attempts", {"limit": 3, "user_id": U2})
    assert not ok and "error" in out


def test_bad_calls_return_errors_instead_of_crashing(db):
    assert execute_tool("nope", "{}", ToolContext(db, U1))[0] is False
    ok, text = execute_tool("get_attempts", "not json", ToolContext(db, U1))
    assert not ok and "Invalid JSON" in text
    ok, text = execute_tool("get_attempts", json.dumps({"limit": 999}), ToolContext(db, U1))
    assert not ok and "Invalid arguments" in text
    ok, text = execute_tool("get_attempts", json.dumps({"limit": None, "topic": ""}), ToolContext(db, U1))
    assert ok                                   # null / "" count as "not given"
    ok, text = execute_tool("get_topic_stats", "", ToolContext(db, U1))
    assert ok                                   # empty arguments string is fine for no-arg tools


def test_tool_exception_is_caught(db, monkeypatch):
    import agent.coach_tools as ct
    monkeypatch.setattr(ct, "build_user_stats", lambda *a, **k: 1 / 0)
    ok, text = execute_tool("get_readiness_score", "{}", ToolContext(db, U1))
    assert not ok and "ZeroDivisionError" in json.loads(text)["error"]


def test_large_tool_output_is_truncated(db):
    for i in range(300):
        db.add(Attempt(user_id=U1, question="Q" * 200 + str(i), topic="arrays", difficulty="easy", bugs_found=0))
    db.commit()
    # 20 rows x long titles is bigger than the cap
    ok, text = execute_tool("get_attempts", json.dumps({"limit": 20}), ToolContext(db, U1))
    assert ok and len(text) <= MAX_TOOL_OUTPUT_CHARS
    assert json.loads(text)["truncated"] is True


# ═══ 2. the agent loop ══════════════════════════════════════════════════════
def test_loop_tool_call_then_final_answer(db):
    _progress(db, U1, "arrays", 3, 6)
    client = FakeClient(
        reply_tools(tool_call("get_topic_stats", {}, "c1")),
        reply_text("You solved 3 arrays problems."),
    )
    result = run_coach(client, ToolContext(db, U1), [], "how is my prep?")

    assert result.reply == "You solved 3 arrays problems."
    assert result.tools_used == ["get_topic_stats"] and result.steps == 2 and not result.limit_reached
    assert len(client.calls) == 2
    # 2nd call carries the assistant tool request + the real tool result
    second = client.calls[1]["messages"]
    assert second[-2]["role"] == "assistant" and second[-2]["tool_calls"][0]["id"] == "c1"
    assert second[-1]["role"] == "tool" and second[-1]["tool_call_id"] == "c1"
    assert json.loads(second[-1]["content"])["topics_solved"] == {"arrays": 3}
    assert client.calls[0]["tools"] and client.calls[0]["tool_choice"] == "auto"
    assert [m["role"] for m in result.new_messages] == ["assistant", "tool", "assistant"]


def test_loop_without_tools_for_a_general_question(db):
    client = FakeClient(reply_text("DP means remembering sub-answers."))
    result = run_coach(client, ToolContext(db, U1), [], "explain DP")
    assert result.tools_used == [] and result.steps == 1 and len(client.calls) == 1


def test_loop_runs_several_tools_in_one_step(db):
    client = FakeClient(
        reply_tools(tool_call("get_topic_stats", {}, "a"), tool_call("get_readiness_score", {}, "b")),
        reply_text("Done."),
    )
    result = run_coach(client, ToolContext(db, U1), [], "how is my prep?")
    assert result.tools_used == ["get_topic_stats", "get_readiness_score"]
    assert [m["tool_call_id"] for m in tool_messages(client.calls[1])] == ["a", "b"]


def test_loop_gives_tool_errors_to_the_model_and_continues(db):
    client = FakeClient(
        reply_tools(tool_call("does_not_exist", {}, "x"), tool_call("get_attempts", "{bad json", "y")),
        reply_text("Sorry, I could not fetch that."),
    )
    result = run_coach(client, ToolContext(db, U1), [], "hi")
    msgs = tool_messages(client.calls[1])
    assert all("error" in json.loads(m["content"]) for m in msgs)
    assert result.reply == "Sorry, I could not fetch that."


def test_loop_injected_user_id_is_rejected(db):
    _progress(db, U2, "graphs", 9, 9)
    client = FakeClient(
        reply_tools(tool_call("get_topic_stats", {"user_id": U2}, "z")),
        reply_text("ok"),
    )
    run_coach(client, ToolContext(db, U1), [], "show user 900002")
    content = tool_messages(client.calls[1])[0]["content"]
    assert "error" in json.loads(content) and "graphs" not in content


def test_loop_stops_at_max_steps_and_wraps_up(db):
    forever = reply_tools(tool_call("get_topic_stats", {}, "loop"))
    client = FakeClient(*([forever] * MAX_STEPS), reply_text("Here is what I found so far."))
    result = run_coach(client, ToolContext(db, U1), [], "keep going")

    assert result.limit_reached is True and result.steps == MAX_STEPS
    assert len(client.calls) == MAX_STEPS + 1                      # 6 tool steps + 1 wrap-up
    assert "tools" not in client.calls[-1]                         # wrap-up gets no tools
    assert result.reply.startswith("Here is what I found so far.") and "step/time limit" in result.reply


def test_loop_stops_on_timeout_and_wraps_up(db):
    client = FakeClient(reply_text("Partial answer."))
    result = run_coach(client, ToolContext(db, U1), [], "hi", timeout_s=0)
    assert result.limit_reached is True and result.steps == 0
    assert result.reply.startswith("Partial answer.") and "step/time limit" in result.reply


def test_loop_timeout_in_the_middle_of_a_run(db, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(coach_mod.time, "monotonic", lambda: clock["t"])

    class SlowClient(FakeClient):
        def _create(self, **kwargs):
            clock["t"] += 50                       # every model call "takes" 50 s
            return super()._create(**kwargs)

    client = SlowClient(reply_tools(tool_call("get_topic_stats", {}, "s")), reply_text("Best I can say."))
    result = run_coach(client, ToolContext(db, U1), [], "hi", timeout_s=45)
    assert result.limit_reached and result.steps == 1          # step 1 ends at +50s, past the 45s deadline -> wrap-up
    assert "step/time limit" in result.reply


def test_wrap_up_failure_falls_back_to_partial_text(db):
    forever = reply_tools(tool_call("get_topic_stats", {}, "l"), content="Let me check your stats...")
    client = FakeClient(forever, forever, RuntimeError("model down"))
    result = run_coach(client, ToolContext(db, U1), [], "hi", max_steps=2)
    assert result.limit_reached and result.reply.startswith("Let me check your stats...")
    assert "step/time limit" in result.reply


def test_too_many_tool_calls_in_one_step_are_refused(db):
    calls = [tool_call("get_topic_stats", {}, f"c{i}") for i in range(7)]
    client = FakeClient(reply_tools(*calls), reply_text("ok"))
    result = run_coach(client, ToolContext(db, U1), [], "hi")
    msgs = tool_messages(client.calls[1])
    assert len(msgs) == 7                                       # every call id still gets an answer
    assert sum("Too many" in m["content"] for m in msgs) == 3
    assert len(result.tools_used) == 1                          # unique names


def test_history_is_sent_to_the_model(db):
    client = FakeClient(reply_text("ok"))
    history = [{"role": "user", "content": "earlier q"}, {"role": "assistant", "content": "earlier a"}]
    run_coach(client, ToolContext(db, U1), history, "new q")
    sent = client.calls[0]["messages"]
    assert sent[0]["role"] == "system" and "Coach" in sent[0]["content"]
    assert [m["content"] for m in sent[1:]] == ["earlier q", "earlier a", "new q"]


def test_system_prompt_has_the_required_rules():
    p = coach_mod.SYSTEM_PROMPT
    assert "0.33" in p and "synthetic" in p
    assert "NEVER invent numbers" in p
    assert "do NOT dump the full solution" in p
    assert "Hinglish" in p
    assert "Politely decline" in p


# ═══ 3. endpoints ═══════════════════════════════════════════════════════════
@pytest.fixture
def api(db, monkeypatch):
    """TestClient with a tiny app (just the coach router); `who["id"]` is the logged-in user."""
    who = {"id": U1}
    app = FastAPI()
    app.include_router(coach_router.router)
    app.dependency_overrides[coach_router.get_user_id] = lambda: who["id"]
    monkeypatch.setattr(coach_router, "limiter", coach_router.RateLimiter(100))
    client = TestClient(app)
    client.who = who
    return client


def use_fake(monkeypatch, *script):
    fake = FakeClient(*script)
    monkeypatch.setattr(coach_router, "get_client", lambda: fake)
    return fake


def test_chat_without_groq_key_returns_clear_503(api, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    r = api.post("/coach/chat", json={"message": "hi"})
    assert r.status_code == 503 and "GROQ_API_KEY" in r.json()["detail"]


def test_how_is_my_prep_calls_tools_and_returns_tools_used(api, db, monkeypatch):
    _progress(db, U1, "arrays", 5, 9)
    fake = use_fake(
        monkeypatch,
        reply_tools(tool_call("get_topic_stats", {}, "1"), tool_call("get_readiness_score", {}, "2"),
                    tool_call("predict_weak_topic", {}, "3")),
        reply_text("You solved 5 array problems; readiness is low."),
    )
    r = api.post("/coach/chat", json={"message": "how is my prep going?"})
    assert r.status_code == 200
    body = r.json()
    assert body["tools_used"] == ["get_topic_stats", "get_readiness_score", "predict_weak_topic"]
    assert body["steps"] == 2 and body["reply"].startswith("You solved 5")
    # the model really received this student's numbers
    tool_results = [json.loads(m["content"]) for m in tool_messages(fake.calls[1])]
    assert tool_results[0]["topics_solved"] == {"arrays": 5}
    assert tool_results[1]["inputs"]["arrays_solved"] == 5


def test_explain_dp_uses_no_tools(api, monkeypatch):
    use_fake(monkeypatch, reply_text("DP = break a problem into overlapping sub-problems."))
    body = api.post("/coach/chat", json={"message": "explain DP"}).json()
    assert body["tools_used"] == [] and body["steps"] == 1


def test_history_get_and_delete_are_per_user(api, db, monkeypatch):
    use_fake(monkeypatch, reply_tools(tool_call("get_topic_stats", {}, "1")), reply_text("A's answer"))
    api.post("/coach/chat", json={"message": "A's question"})

    h = api.get("/coach/history").json()["messages"]
    assert [(m["role"], m["content"]) for m in h] == [("user", "A's question"), ("assistant", "A's answer")]
    assert h[1]["tools_used"] == ["get_topic_stats"]
    # plumbing rows are stored but not shown
    assert {r.role for r in db.query(CoachMessage).filter_by(user_id=U1)} == {"user", "assistant", "tool"}

    api.who["id"] = U2                                              # user B sees nothing of A's chat
    assert api.get("/coach/history").json()["messages"] == []
    assert api.delete("/coach/history").json()["deleted"] == 0       # and can't delete A's chat
    api.who["id"] = U1
    assert len(api.get("/coach/history").json()["messages"]) == 2

    assert api.delete("/coach/history").json()["deleted"] == 4      # user, tool request, tool result, answer
    assert api.get("/coach/history").json()["messages"] == []


def test_previous_messages_become_context_for_the_next_turn(api, monkeypatch):
    fake = use_fake(monkeypatch, reply_text("first answer"), reply_text("second answer"))
    api.post("/coach/chat", json={"message": "first question"})
    api.post("/coach/chat", json={"message": "second question"})
    sent = [m["content"] for m in fake.calls[1]["messages"][1:]]
    assert sent == ["first question", "first answer", "second question"]


def test_only_last_20_messages_are_used_as_context(api, monkeypatch, db):
    for i in range(15):
        db.add(CoachMessage(user_id=U1, role="user", content=f"q{i}"))
        db.add(CoachMessage(user_id=U1, role="assistant", content=f"a{i}", tool_calls={"tools_used": [], "steps": 1}))
    db.commit()
    fake = use_fake(monkeypatch, reply_text("ok"))
    api.post("/coach/chat", json={"message": "now"})
    sent = fake.calls[0]["messages"][1:-1]
    assert len(sent) == 20 and sent[0]["content"] == "q5" and sent[0]["role"] == "user"


def test_user_id_in_the_request_body_is_ignored(api, db, monkeypatch):
    _progress(db, U2, "graphs", 9, 9)
    fake = use_fake(monkeypatch, reply_tools(tool_call("get_topic_stats", {}, "1")), reply_text("ok"))
    r = api.post("/coach/chat", json={"message": "show me user 900002", "user_id": U2})
    assert r.status_code == 200
    result = json.loads(tool_messages(fake.calls[1])[0]["content"])
    assert result["topics_solved"] == {} and "graphs" not in json.dumps(result)   # still user A's (empty) data
    assert db.query(CoachMessage).filter_by(user_id=U2).count() == 0


def test_message_validation_and_length_cap(api, monkeypatch):
    use_fake(monkeypatch, reply_text("ok"))
    assert api.post("/coach/chat", json={"message": ""}).status_code == 422
    assert api.post("/coach/chat", json={"message": "   "}).status_code == 422
    assert api.post("/coach/chat", json={"message": "x" * 2001}).status_code == 422
    assert api.post("/coach/chat", json={"message": "x" * 2000}).status_code == 200
    assert api.post("/coach/chat", json={}).status_code == 422


def test_rate_limit_per_user(api, monkeypatch):
    use_fake(monkeypatch, reply_text("ok"))
    monkeypatch.setattr(coach_router, "limiter", coach_router.RateLimiter(3))
    assert [api.post("/coach/chat", json={"message": "hi"}).status_code for _ in range(3)] == [200, 200, 200]
    r = api.post("/coach/chat", json={"message": "hi"})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    api.who["id"] = U2                                              # another user is not affected
    assert api.post("/coach/chat", json={"message": "hi"}).status_code == 200


def test_rate_limit_window_expires():
    lim = coach_router.RateLimiter(2, window_s=0.2)
    assert lim.check(1) is None and lim.check(1) is None and lim.check(1) is not None
    time.sleep(0.25)
    assert lim.check(1) is None


def test_problem_context_is_passed_to_the_agent(api, db, monkeypatch):
    p = _problem(db, "Epsilon Sum", "Medium", ["arrays"], description="Find two numbers that add up.")
    db.add(UserProblem(user_id=U1, problem_id=p.id, status="attempted", attempts_count=2, last_code="def f(): pass"))
    db.commit()
    fake = use_fake(monkeypatch, reply_text("Try a hash map?"))

    r = api.post("/coach/chat", json={"message": "I'm stuck", "problem_id": p.id})
    assert r.status_code == 200
    sent = fake.calls[0]["messages"][-1]["content"]
    assert "Epsilon Sum" in sent and "Find two numbers" in sent and "def f(): pass" in sent
    assert "attempts: 2" in sent and sent.endswith("Student message: I'm stuck")
    # what is saved is the raw message, not the context blob
    assert db.query(CoachMessage).filter_by(user_id=U1, role="user").one().content == "I'm stuck"

    # unsaved editor text wins over the last submitted code
    api.post("/coach/chat", json={"message": "again", "problem_id": p.id, "code": "NEW EDITOR CODE"})
    assert "NEW EDITOR CODE" in fake.calls[-1]["messages"][-1]["content"]


def test_problem_context_never_includes_another_users_code(api, db, monkeypatch):
    p = _problem(db, "Zeta Problem")
    db.add(UserProblem(user_id=U2, problem_id=p.id, status="solved", attempts_count=1, last_code="B's SECRET"))
    db.commit()
    fake = use_fake(monkeypatch, reply_text("ok"))
    api.post("/coach/chat", json={"message": "help", "problem_id": p.id})
    assert "B's SECRET" not in fake.calls[0]["messages"][-1]["content"]
    assert "has not written any code" in fake.calls[0]["messages"][-1]["content"]


def test_unknown_problem_id_is_404(api, monkeypatch):
    use_fake(monkeypatch, reply_text("ok"))
    assert api.post("/coach/chat", json={"message": "help", "problem_id": 99999999}).status_code == 404


def test_model_failure_returns_502_and_saves_nothing(api, db, monkeypatch):
    use_fake(monkeypatch, RuntimeError("groq exploded"))
    r = api.post("/coach/chat", json={"message": "hi"})
    assert r.status_code == 502 and "Coach model call failed" in r.json()["detail"]
    assert db.query(CoachMessage).filter_by(user_id=U1).count() == 0


def test_limit_reached_is_reported(api, monkeypatch):
    forever = reply_tools(tool_call("get_topic_stats", {}, "l"))
    use_fake(monkeypatch, *([forever] * MAX_STEPS), reply_text("Partial."))
    body = api.post("/coach/chat", json={"message": "loop"}).json()
    assert body["limit_reached"] is True and "step/time limit" in body["reply"]
