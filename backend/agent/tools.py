"""
Agent ke saare tools yahin hain. Ye normal Python functions hain, LLM inhe
khud nahi chalata, wo sirf naam + arguments bolta hai, chalate hum hain.
Har tool dict return karta hai. Error aaye to {"error": "..."} (crash nahi).
"""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from agent.sandbox import run_code_against_tests
from models import InterviewSession, TopicProgress, WeakPattern

QUESTIONS_PATH = Path(__file__).parent / "questions.json"
SCORE_KEYS = ("approach", "complexity", "edge_cases", "communication")   # fixed rubric, har ek 0-5


def load_questions() -> list:
    with open(QUESTIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _get_question(qid: str):
    return next((q for q in load_questions() if q["id"] == qid), None)


# ── Tool 1: pick_question ──────────────────────────────────────────────────
def pick_question(db: Session, session: InterviewSession, topic: str = "", level: str = "") -> dict:
    asked = json.loads(session.asked_question_ids or "[]")
    pool = [q for q in load_questions() if q["id"] not in asked]
    topic, level = (topic or "").lower().strip(), (level or "").lower().strip()

    def match(q, use_topic, use_level):
        return (not use_topic or topic in q["topic"]) and (not use_level or q["level"] == level)

    # Pehle exact match, phir level dheela, phir topic dheela, phir kuch bhi
    for use_topic, use_level in ((True, True), (True, False), (False, True), (False, False)):
        matches = [q for q in pool if match(q, use_topic, use_level)]
        if matches:
            q = matches[0]
            break
    else:
        return {"error": "No unasked questions left. Wrap up with save_scorecard."}

    asked.append(q["id"])
    session.asked_question_ids = json.dumps(asked)
    session.current_question_id = q["id"]
    session.hints_used = 0
    db.commit()
    # NOTE: tests, hints, solution LLM ko nahi bhejte, sirf statement + follow_ups
    return {k: q[k] for k in ("id", "title", "topic", "level", "statement", "function", "follow_ups")}


# ── Tool 2: get_hint ───────────────────────────────────────────────────────
def get_hint(db: Session, session: InterviewSession) -> dict:
    q = _get_question(session.current_question_id or "")
    if not q:
        return {"error": "No active question. Call pick_question first."}
    if session.hints_used >= len(q["hints"]):
        return {"error": "No more hints available for this question."}
    hint = q["hints"][session.hints_used]          # hint level server decide karta hai, LLM nahi
    session.hints_used += 1
    db.commit()
    return {"hint_number": session.hints_used, "of": len(q["hints"]), "hint": hint}


# ── Tool 3: run_tests ──────────────────────────────────────────────────────
def run_tests(db: Session, session: InterviewSession, code: str = "") -> dict:
    q = _get_question(session.current_question_id or "")
    if not q:
        return {"error": "No active question. Call pick_question first."}
    return run_code_against_tests(code, q["function"], q["tests"], q.get("compare", "exact"))


# ── Tool 4: get_user_history ───────────────────────────────────────────────
def get_user_history(db: Session, session: InterviewSession) -> dict:
    weak = (db.query(WeakPattern).filter(WeakPattern.user_id == session.user_id)
            .order_by(WeakPattern.count.desc()).limit(5).all())
    topics = db.query(TopicProgress).filter(TopicProgress.user_id == session.user_id).all()
    return {
        "weak_patterns": [{"pattern": w.pattern, "times_flagged": w.count} for w in weak],
        "topic_progress": [{"topic": t.topic, "solved": t.count, "attempts": t.total_attempts} for t in topics],
    }


# ── Tool 5: save_scorecard ─────────────────────────────────────────────────
def save_scorecard(db: Session, session: InterviewSession, approach=None, complexity=None,
                   edge_cases=None, communication=None, weak_patterns=None, summary: str = "") -> dict:
    raw = {"approach": approach, "complexity": complexity, "edge_cases": edge_cases, "communication": communication}
    scores = {}
    for key in SCORE_KEYS:
        v = raw[key]
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 5:
            return {"error": f"'{key}' must be an integer between 0 and 5, got {v!r}."}
        scores[key] = v

    patterns = [str(p).strip().lower()[:60] for p in (weak_patterns or []) if str(p).strip()][:5]
    scorecard = {**scores, "total": sum(scores.values()), "out_of": 20,
                 "weak_patterns": patterns, "summary": (summary or "")[:600]}

    session.scorecard = json.dumps(scorecard)
    session.status = "finished"
    for p in patterns:                       # Interview -> Coach ko jodne wali cheez
        row = db.query(WeakPattern).filter(WeakPattern.user_id == session.user_id, WeakPattern.pattern == p).first()
        if row:
            row.count += 1
        else:
            db.add(WeakPattern(user_id=session.user_id, pattern=p, count=1, source="interview"))
    db.commit()
    return {"saved": True, "scorecard": scorecard}


# ── Coach Agent / /analyze ke liye helper ──────────────────────────────────
def get_weak_patterns_text(db: Session, user_id: int) -> str:
    rows = (db.query(WeakPattern).filter(WeakPattern.user_id == user_id)
            .order_by(WeakPattern.count.desc()).limit(3).all())
    if not rows:
        return "No known weak patterns yet."
    return ", ".join(f"{r.pattern} (flagged {r.count}x)" for r in rows)


# ── Dispatcher ─────────────────────────────────────────────────────────────
TOOL_FUNCS = {
    "pick_question": pick_question, "get_hint": get_hint, "run_tests": run_tests,
    "get_user_history": get_user_history, "save_scorecard": save_scorecard,
}


def execute_tool(name: str, args: dict, db: Session, session: InterviewSession) -> dict:
    fn = TOOL_FUNCS.get(name)
    if not fn:
        return {"error": f"Unknown tool '{name}'."}
    try:
        return fn(db, session, **(args or {}))
    except TypeError as e:                   # LLM ne galat arguments bheje
        return {"error": f"Bad arguments for {name}: {e}"}
    except Exception as e:
        db.rollback()
        return {"error": f"{name} failed: {type(e).__name__}: {e}"}


def _obj(props, required=()):
    return {"type": "object", "properties": props, "required": list(required)}


TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": "get_user_history",
        "description": "Get the candidate's known weak patterns and topic progress. Call once at the start.",
        "parameters": _obj({})}},
    {"type": "function", "function": {"name": "pick_question",
        "description": "Pick the next unasked interview question from the question bank. Returns statement and follow-up questions.",
        "parameters": _obj({"topic": {"type": "string", "description": "e.g. arrays, dp, stack, hashing, sliding window, binary search"},
                            "level": {"type": "string", "enum": ["easy", "medium", "hard"]}})}},
    {"type": "function", "function": {"name": "get_hint",
        "description": "Get the next hint for the current question. Use only when the candidate is stuck. Hints get progressively more revealing.",
        "parameters": _obj({})}},
    {"type": "function", "function": {"name": "run_tests",
        "description": "Run the candidate's Python code against the current question's hidden tests.",
        "parameters": _obj({"code": {"type": "string", "description": "The candidate's full Python code"}}, ["code"])}},
    {"type": "function", "function": {"name": "save_scorecard",
        "description": "End the interview and save the final scorecard. Each score is an integer 0-5.",
        "parameters": _obj({"approach": {"type": "integer"}, "complexity": {"type": "integer"},
                            "edge_cases": {"type": "integer"}, "communication": {"type": "integer"},
                            "weak_patterns": {"type": "array", "items": {"type": "string"},
                                              "description": "Up to 5 short DSA pattern names the candidate struggled with, e.g. 'sliding window'"},
                            "summary": {"type": "string"}},
                           ["approach", "complexity", "edge_cases", "communication"])}},
]
