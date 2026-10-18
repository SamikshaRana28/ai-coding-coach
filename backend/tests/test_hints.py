"""Tests for Part 4: the hint system (endpoint, levels, cache, stats, Coach tool). LLM is faked."""
import json
import re

import pytest

import hints as hint_mod
from tests.conftest import SEED_ROWS

CODE = "def two_sum(nums, target):\n    return []"


# ── helpers ───────────────────────────────────────────────────────────────────
class FakeLLM:
    """Stands in for hints.llm_complete: canned text per level, records every call."""

    def __init__(self):
        self.calls = []
        self.replies = []      # if set, popped in order instead of the default text
        self.error = None

    def __call__(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        if self.replies:
            return self.replies.pop(0)
        level = int(re.search(r"hint level (\d)", messages[1]["content"]).group(1))
        return f"Plain-English hint number {level}."


@pytest.fixture()
def llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(hint_mod, "llm_complete", fake)
    return fake


def pid(api, slug="two-sum"):
    items = api.client.get("/problems", params={"page_size": 100}).json()["items"]
    return {p["slug"]: p["id"] for p in items}[slug]


def hint(api, problem_id, headers=None, body=None):
    return api.client.post(f"/problems/{problem_id}/hint", json=body, headers=headers or {})


# ── endpoint: levels, order, cache ────────────────────────────────────────────
def test_hint_requires_login(api):
    from fastapi.testclient import TestClient

    anon = TestClient(api.main.app)
    assert anon.post(f"/problems/{pid(api)}/hint").status_code == 401


def test_hints_unlock_one_level_at_a_time(api, llm):
    p = pid(api)
    seen = []
    for expected in (1, 2, 3):
        r = hint(api, p)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["level"] == expected and d["new"] is True and d["hints_used"] == expected
        assert d["hint"] == f"Plain-English hint number {expected}."
        assert d["max_level"] == 3
        assert d["next_level"] == (expected + 1 if expected < 3 else None)
        seen.append(d["hint"])
        assert [h["level"] for h in d["unlocked"]] == list(range(1, expected + 1))   # earlier ones stay visible
    assert len(llm.calls) == 3


def test_after_level_3_clicking_again_returns_the_stored_hint(api, llm):
    p = pid(api)
    for _ in range(3):
        hint(api, p)
    again = hint(api, p).json()
    assert again["level"] == 3 and again["new"] is False and again["next_level"] is None
    assert again["hints_used"] == 3
    assert len(llm.calls) == 3                       # no 4th LLM call


def test_asking_for_an_unlocked_level_is_served_from_storage(api, llm):
    p = pid(api)
    first = hint(api, p).json()["hint"]
    hint(api, p)
    calls_before = len(llm.calls)
    again = hint(api, p, body={"level": 1}).json()
    assert again["hint"] == first and again["new"] is False and again["level"] == 1
    assert again["hints_used"] == 2                  # asking for an old level does not lower or raise it
    assert len(llm.calls) == calls_before


def test_levels_cannot_be_skipped(api, llm):
    p = pid(api)
    r = hint(api, p, body={"level": 3})
    assert r.status_code == 409 and "Unlock hint 1 first" in r.json()["detail"]
    assert llm.calls == []
    assert api.client.get(f"/problems/{p}").json()["hints_used"] == 0
    hint(api, p)
    assert hint(api, p, body={"level": 3}).status_code == 409        # still needs level 2
    assert hint(api, p, body={"level": 2}).status_code == 200        # the next one is fine


def test_invalid_level_and_unknown_problem(api, llm):
    p = pid(api)
    assert hint(api, p, body={"level": 0}).status_code == 422
    assert hint(api, p, body={"level": 4}).status_code == 422
    assert hint(api, 99999).status_code == 404
    assert llm.calls == []


# ── reopening, per-user isolation, list/detail ────────────────────────────────
def test_reopening_the_problem_shows_unlocked_hints(api, llm):
    p = pid(api)
    hint(api, p)
    hint(api, p)
    detail = api.client.get(f"/problems/{p}").json()
    assert detail["hints_used"] == 2 and detail["max_hint_level"] == 3
    assert detail["hints"] == [
        {"level": 1, "text": "Plain-English hint number 1."},
        {"level": 2, "text": "Plain-English hint number 2."},
    ]


def test_hints_are_per_user(api, llm):
    p = pid(api)
    hint(api, p)
    hint(api, p)
    second = hint(api, p, headers=api.h2).json()
    assert second["level"] == 1 and second["hints_used"] == 1       # user 2 starts from level 1
    assert api.client.get(f"/problems/{p}", headers=api.h2).json()["hints"] == [
        {"level": 1, "text": "Plain-English hint number 1."}]
    assert api.client.get(f"/problems/{p}").json()["hints_used"] == 2


def test_x_user_id_header_cannot_unlock_hints_for_someone_else(api, llm):
    p = pid(api)
    r = api.client.post(f"/problems/{p}/hint", headers={"X-User-Id": "2"})   # still user 1's token
    assert r.status_code == 200
    assert api.client.get(f"/problems/{p}", headers=api.h2).json()["hints_used"] == 0


def test_hints_used_is_in_the_problem_list(api, llm):
    p = pid(api)
    hint(api, p)
    hint(api, p)
    items = {x["id"]: x for x in api.client.get("/problems", params={"page_size": 100}).json()["items"]}
    assert items[p]["hints_used"] == 2
    assert all(x["hints_used"] == 0 for i, x in items.items() if i != p)


def test_hints_used_survives_submitting_code(api, llm):
    p = pid(api)
    hint(api, p)
    sub = api.client.post(f"/problems/{p}/submit", json={"code": CODE, "language": "python"}).json()
    assert sub["hints_used"] == 1
    assert api.client.get(f"/problems/{p}").json()["hints"][0]["level"] == 1


# ── prompt content ────────────────────────────────────────────────────────────
def test_prompt_forbids_solutions_and_carries_context(api, llm):
    p = pid(api)
    hint(api, p, body={"code": "my_unsaved_editor_code()"})
    system, user = llm.calls[0][0]["content"], llm.calls[0][1]["content"]
    assert "NEVER output the final code solution" in system
    assert "Two Sum" in user and SEED_ROWS[0]["description"] in user
    assert "my_unsaved_editor_code()" in user                       # editor text is used
    assert "LEVEL 1" in user and "Do NOT name the algorithm" in user

    hint(api, p)
    user2 = llm.calls[1][1]["content"]
    assert "Plain-English hint number 1." in user2 and "LEVEL 2" in user2   # previous hints are passed on
    assert "my_unsaved_editor_code()" not in user2                  # the editor text was never saved


def test_prompt_falls_back_to_last_submitted_code(api, llm):
    p = pid(api)
    api.client.post(f"/problems/{p}/submit", json={"code": "print('saved')", "language": "python"})
    hint(api, p)
    assert "print('saved')" in llm.calls[0][1]["content"]


def test_level_3_prompt_asks_for_pseudocode_not_working_code(api, llm):
    p = pid(api)
    for _ in range(3):
        hint(api, p)
    level3 = llm.calls[2][1]["content"]
    assert "LEVEL 3" in level3 and "pseudo-code" in level3 and "NOT be working code" in level3


# ── no solution code ever comes back ──────────────────────────────────────────
def test_code_in_the_answer_is_retried_then_replaced(api, llm):
    p = pid(api)
    llm.replies = [
        "Here you go:\n```python\ndef two_sum(nums, target):\n    return []\n```",
        "Think about what you have already seen while scanning the list.",
    ]
    d = hint(api, p).json()
    assert d["hint"] == "Think about what you have already seen while scanning the list."
    assert len(llm.calls) == 2
    assert "contained code" in llm.calls[1][2]["content"]            # the retry carries the strict reminder


def test_code_that_keeps_coming_back_is_stripped_to_a_safe_hint(api, llm):
    p = pid(api)
    bad = "```python\ndef two_sum(nums, target):\n    seen = {}\n    return []\n```"
    llm.replies = [bad, bad]
    d = hint(api, p).json()
    assert "```" not in d["hint"] and "def " not in d["hint"]
    assert d["hint"] == hint_mod.FALLBACK_HINTS[1]                   # nothing usable left -> generic hint
    assert d["hints_used"] == 1


def test_guard_detects_code_but_not_plain_advice():
    g = hint_mod.contains_solution_code
    assert g("```\nx = 1\n```")
    assert g("def solve(nums):\n    pass")
    assert g("class Solution {\n}")
    assert g("int x = 0;\nreturn x;")
    assert g("#include <vector>")
    assert not g("Use a hash map so each lookup is O(1). Think about `complement = target - x`.")
    assert not g("1. Walk through the list.\n2. For each number, check whether its partner was seen.\n3. Return the pair.")
    assert hint_mod.strip_code("Keep this.\n```\ncode()\n```\nAnd this.") == "Keep this.\n\nAnd this."


# ── failures cost nothing ─────────────────────────────────────────────────────
def test_llm_failure_writes_nothing_and_charges_no_hint(api, llm):
    p = pid(api)
    llm.error = hint_mod.HintUnavailable("The AI model could not be reached. Please try again in a moment.")
    r = hint(api, p)
    assert r.status_code == 503 and "could not be reached" in r.json()["detail"]
    detail = api.client.get(f"/problems/{p}").json()
    assert detail["hints_used"] == 0 and detail["hints"] == []

    llm.error = None
    assert hint(api, p).json()["level"] == 1                          # the retry starts at level 1


def test_missing_api_key_is_a_clear_503(api, monkeypatch):
    import analysis

    monkeypatch.setattr(analysis, "client", None)
    r = hint(api, pid(api))
    assert r.status_code == 503 and "GROQ_API_KEY" in r.json()["detail"]


def test_hint_rate_limit_counts_only_generated_hints(api, llm, monkeypatch):
    from coach_router import RateLimiter
    from routers import problems as problems_router

    monkeypatch.setattr(problems_router, "hint_limiter", RateLimiter(2))
    a, b = pid(api, "two-sum"), pid(api, "add-two-numbers")
    assert hint(api, a).status_code == 200
    assert hint(api, a, body={"level": 1}).status_code == 200         # cached: not counted
    assert hint(api, b).status_code == 200
    r = hint(api, a)                                                   # 3rd generation within the minute
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    assert api.client.get(f"/problems/{a}").json()["hints_used"] == 1  # nothing was charged


def test_two_clicks_at_once_store_one_hint(api):
    """If another request unlocks the same level while the LLM is busy, we serve the stored one."""
    from models import HintEvent, Problem

    db = api.Session()
    problem = db.query(Problem).first()

    def racing_generator(problem, level, code, previous):
        other = api.Session()                                          # the "second click"
        other.add(HintEvent(user_id=1, problem_id=problem.id, level=level, hint_text="first click wins"))
        other.commit()
        other.close()
        return "second click text"

    result = hint_mod.reveal_hint(db, 1, problem, generator=racing_generator)
    assert result.text == "first click wins" and result.is_new is False
    assert db.query(HintEvent).filter_by(user_id=1, problem_id=problem.id).count() == 1
    db.close()


# ── dashboard stats ───────────────────────────────────────────────────────────
def test_problem_stats_count_solved_without_hints(api, llm):
    a, b, c = pid(api, "two-sum"), pid(api, "add-two-numbers"), pid(api, "number-of-islands")
    api.client.post(f"/problems/{a}/mark-solved")                       # solved, no hints
    hint(api, b)
    hint(api, b)
    api.client.post(f"/problems/{b}/mark-solved")                       # solved with 2 hints
    hint(api, c)                                                         # hint but unsolved
    api.client.post(f"/problems/{c}/submit", json={"code": CODE})        # clean fake review -> solved
    api.llm.bugs = "Off-by-one error"
    api.client.post(f"/problems/{pid(api, 'merge-k-sorted-lists')}/submit", json={"code": CODE})   # attempted

    s = api.client.get("/problem-stats").json()
    assert s["solved"] == 3 and s["solved_without_hints"] == 1 and s["solved_with_hints"] == 2
    assert s["attempted"] == 1 and s["total_hints_used"] == 3
    assert api.client.get("/problem-stats", headers=api.h2).json() == {
        "solved": 0, "solved_without_hints": 0, "solved_with_hints": 0, "attempted": 0, "total_hints_used": 0}


def test_problem_stats_requires_login(api):
    from fastapi.testclient import TestClient

    assert TestClient(api.main.app).get("/problem-stats").status_code == 401


# ── Coach tool ────────────────────────────────────────────────────────────────
def run_tool(api, user_id, args, name="get_hint"):
    from agent.coach_tools import ToolContext, execute_tool

    db = api.Session()
    try:
        ok, out = execute_tool(name, json.dumps(args), ToolContext(db=db, user_id=user_id))
    finally:
        db.close()
    return ok, json.loads(out)


def test_coach_tool_is_registered_and_cannot_pick_a_level_or_user():
    from agent.coach_tools import tool_schemas

    schema = next(s for s in tool_schemas() if s["function"]["name"] == "get_hint")
    assert set(schema["function"]["parameters"]["properties"]) == {"problem_id"}
    assert "user_id" not in json.dumps(schema)


def test_coach_tool_uses_the_same_levels_and_cache_as_the_button(api, llm):
    p = pid(api)
    ok, first = run_tool(api, 1, {"problem_id": p})
    assert ok and first["hint_level"] == 1 and first["of"] == 3 and first["newly_unlocked"] is True
    assert first["hint"] == "Plain-English hint number 1."
    # the button continues where the Coach stopped
    assert hint(api, p).json()["level"] == 2
    ok, third = run_tool(api, 1, {"problem_id": p})
    assert third["hint_level"] == 3
    ok, fourth = run_tool(api, 1, {"problem_id": p})
    assert fourth["newly_unlocked"] is False and "All 3 hints are already used" in fourth["note"]
    assert len(llm.calls) == 3
    assert api.client.get(f"/problems/{p}").json()["hints_used"] == 3


def test_coach_tool_works_for_the_calling_student_only(api, llm):
    p = pid(api)
    run_tool(api, 1, {"problem_id": p})
    ok, theirs = run_tool(api, 2, {"problem_id": p})
    assert theirs["hint_level"] == 1                                     # user 2 has their own progress


def test_coach_tool_errors_are_returned_not_raised(api, llm):
    ok, out = run_tool(api, 1, {"problem_id": 99999})
    assert not ok and "No problem" in out["error"]
    ok, out = run_tool(api, 1, {"problem_id": pid(api), "level": 3})
    assert not ok and "Invalid arguments" in out["error"]
    ok, out = run_tool(api, 1, {"problem_id": pid(api), "user_id": 2})
    assert not ok and "Invalid arguments" in out["error"]
    llm.error = hint_mod.HintUnavailable("The AI model could not be reached. Please try again in a moment.")
    ok, out = run_tool(api, 1, {"problem_id": pid(api)})
    assert not ok and "could not be reached" in out["error"]


def test_coach_prompt_only_offers_hints_on_request():
    from agent import coach

    assert "get_hint only when the student asks" in coach.SYSTEM_PROMPT
    assert "Never call get_hint on your own" in coach.SYSTEM_PROMPT


def test_coach_context_contains_the_problem_id(api):
    import coach_router

    db = api.Session()
    try:
        ctx = coach_router._problem_context(db, 1, pid(api), None)
    finally:
        db.close()
    assert f"problem id {pid(api)}" in ctx
