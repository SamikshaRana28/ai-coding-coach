"""
coach_tools.py - the tools the Coach agent can call.

Every tool wraps code that already exists (user_stats, ml.*, the tables) -
no new ML or scoring logic lives here.

SECURITY: `user_id` is NOT an argument of any tool. The server puts the logged-in
user's id into ToolContext, and every query below filters on ctx.user_id. The
argument models use extra="forbid", so if the model tries to pass a user_id (or
anything else unknown) the call is rejected with an error.
"""
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import String, and_, cast, func, or_
from sqlalchemy.orm import Session

# ADAPT: these class names must match your Part 2 models (problems / user_problems tables)
from models import Attempt, Problem, UserProblem
from user_stats import CORE_TOPICS, STAT_KEYS, build_user_stats, topic_stats

APP_TOPICS = ["arrays", "dp", "graphs", "trees", "strings", "math", "others"]   # the app's topic names
LOW_DATA_ATTEMPTS = 15          # below this, ML output is very uncertain
MAX_TOOL_OUTPUT_CHARS = 3000    # keep tool results small (tokens)
WEAK_MODEL_NOTE = (
    "The weak-topic model was trained mostly on synthetic data and is weak on real users "
    "(real-only holdout F1 about 0.33). Treat it as ONE signal and check it against the plain stats."
)


@dataclass
class ToolContext:
    db: Session
    user_id: int      # injected by the server, never chosen by the model


# ── argument models ─────────────────────────────────────────────────────────
class Args(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _drop_empty(cls, data):
        # models often send null / "" for optional args -> treat as "not given"
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if v is not None and v != ""}
        return data


class NoArgs(Args):
    pass


class GetAttemptsArgs(Args):
    limit: int = Field(5, ge=1, le=20, description="How many recent attempts to return")
    topic: Optional[str] = Field(None, max_length=50, description="Only this topic, e.g. arrays, dp")


class TitleArgs(Args):
    title: str = Field(min_length=1, max_length=200, description="Question title, e.g. Two Sum")
    limit: int = Field(3, ge=1, le=5, description="How many similar questions")


class DifficultyArgs(Args):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000, description="Problem statement, if known")


class SearchProblemsArgs(Args):
    topic: Optional[str] = Field(None, description=f"One of {APP_TOPICS}")
    difficulty: Optional[str] = Field(None, description="Easy, Medium or Hard")
    status: Optional[str] = Field(None, description="todo, attempted or solved (for this student)")
    limit: int = Field(5, ge=1, le=10)

    @field_validator("topic")
    @classmethod
    def _topic(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        if v not in APP_TOPICS:
            raise ValueError(f"topic must be one of {APP_TOPICS}")
        return v

    @field_validator("difficulty")
    @classmethod
    def _difficulty(cls, v):
        if v is None:
            return v
        v = v.strip().capitalize()
        if v not in ("Easy", "Medium", "Hard"):
            raise ValueError("difficulty must be Easy, Medium or Hard")
        return v

    @field_validator("status")
    @classmethod
    def _status(cls, v):
        if v is None:
            return v
        v = v.strip().lower()
        if v not in ("todo", "attempted", "solved"):
            raise ValueError("status must be todo, attempted or solved")
        return v


class GetProblemArgs(Args):
    problem_id: int = Field(ge=1)


# ── tool functions (each returns a small JSON-able dict) ────────────────────
def _data_flags(total_attempts: int) -> dict:
    return {"total_attempts": total_attempts, "low_data": total_attempts < LOW_DATA_ATTEMPTS}


def t_get_topic_stats(ctx: ToolContext, args: NoArgs) -> dict:
    s = topic_stats(ctx.db, ctx.user_id)           # existing /topic-stats logic
    return {
        "topics_solved": s["topics"],
        "acceptance_rate": s["acceptance_rate"],
        **_data_flags(s["total_attempts"]),
    }


def t_get_attempts(ctx: ToolContext, args: GetAttemptsArgs) -> dict:
    q = ctx.db.query(Attempt).filter(Attempt.user_id == ctx.user_id)
    if args.topic:
        q = q.filter(func.lower(Attempt.topic) == args.topic.strip().lower())
    rows = q.order_by(Attempt.created_at.desc(), Attempt.id.desc()).limit(args.limit).all()
    return {
        "count": len(rows),
        "attempts": [
            {
                "question": a.question,
                "topic": a.topic,
                "difficulty": a.difficulty,
                "time_complexity": a.time_complexity,
                "space_complexity": a.space_complexity,
                "had_bugs": bool(a.bugs_found),
                "when": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ],
    }


def t_get_readiness_score(ctx: ToolContext, args: NoArgs) -> dict:
    from ml.score import calculate_readiness_score   # existing scorer

    stats = build_user_stats(ctx.db, ctx.user_id)
    result = calculate_readiness_score(**{k: stats[k] for k in STAT_KEYS})
    return {
        **result,
        "inputs": {k: stats[k] for k in STAT_KEYS},
        **_data_flags(stats["total_attempts"]),
    }


def t_predict_weak_topic(ctx: ToolContext, args: NoArgs) -> dict:
    from ml.predict import predict_weak_topic        # existing XGBoost model

    stats = build_user_stats(ctx.db, ctx.user_id)
    flags = _data_flags(stats["total_attempts"])
    solved = {t: stats[f"{t}_solved"] for t in CORE_TOPICS}
    plain_signal = {
        "solved_per_topic": solved,
        "fewest_solved": sorted(solved, key=lambda t: (solved[t], t))[:2],
        "acceptance_rate": stats["acceptance_rate"],
    }
    if stats["total_attempts"] == 0:
        return {
            "model_prediction": None,
            "plain_stats": plain_signal,
            **flags,
            "note": "No attempts yet, so there is nothing to predict from.",
        }
    pred = predict_weak_topic(**{k: stats[k] for k in STAT_KEYS})
    return {
        "model_prediction": pred,
        "plain_stats": plain_signal,
        **flags,
        "reliability_note": WEAK_MODEL_NOTE,
    }


def t_get_similar_questions(ctx: ToolContext, args: TitleArgs) -> dict:
    from ml.recommender import get_similar_questions   # existing recommender (lazy: loads embeddings)

    return {"similar": get_similar_questions(args.title, top_n=args.limit)}


def t_predict_difficulty(ctx: ToolContext, args: DifficultyArgs) -> dict:
    from ml.difficulty_predict import predict_difficulty   # existing classifier

    return predict_difficulty(args.title, args.description or "")


def t_search_problems(ctx: ToolContext, args: SearchProblemsArgs) -> dict:
    # status is per-user -> join only THIS user's rows
    q = ctx.db.query(Problem, UserProblem.status).outerjoin(
        UserProblem,
        and_(UserProblem.problem_id == Problem.id, UserProblem.user_id == ctx.user_id),
    )
    if args.difficulty:
        q = q.filter(Problem.difficulty == args.difficulty)
    if args.topic:
        q = q.filter(cast(Problem.topics, String).like(f'%"{args.topic}"%'))
    if args.status == "todo":
        q = q.filter(or_(UserProblem.status.is_(None), UserProblem.status == "todo"))
    elif args.status:
        q = q.filter(UserProblem.status == args.status)
    rows = q.order_by(Problem.id).limit(args.limit).all()
    return {
        "count": len(rows),
        "problems": [
            {
                "id": p.id,
                "title": p.title,
                "difficulty": p.difficulty,
                "topics": p.topics,
                "status": st or "todo",
            }
            for p, st in rows
        ],
    }


def t_get_problem(ctx: ToolContext, args: GetProblemArgs) -> dict:
    p = ctx.db.get(Problem, args.problem_id)
    if not p:
        return {"error": f"No problem with id {args.problem_id}"}
    up = (
        ctx.db.query(UserProblem)
        .filter(UserProblem.user_id == ctx.user_id, UserProblem.problem_id == p.id)
        .first()
    )
    return {
        "id": p.id,
        "title": p.title,
        "difficulty": p.difficulty,
        "topics": p.topics,
        "description": (p.description or "")[:1500],
        "your_status": up.status if up else "todo",
        "your_attempts": up.attempts_count if up else 0,
        "hints_used": up.hints_used if up else 0,
        "your_last_code": (up.last_code or "")[:1500] if up else "",
    }


# ── registry ────────────────────────────────────────────────────────────────
@dataclass
class Tool:
    name: str
    description: str
    args_model: Type[Args]
    fn: Callable[[ToolContext, Any], dict]


TOOLS: Dict[str, Tool] = {
    t.name: t
    for t in [
        Tool("get_topic_stats",
             "Solved count per topic and overall acceptance rate for the current student.",
             NoArgs, t_get_topic_stats),
        Tool("get_attempts",
             "The student's most recent code attempts (question, topic, complexity, whether it had bugs).",
             GetAttemptsArgs, t_get_attempts),
        Tool("get_readiness_score",
             "Interview readiness score (0-100) with breakdown, computed from the student's real data.",
             NoArgs, t_get_readiness_score),
        Tool("predict_weak_topic",
             "ML prediction of the student's weakest topic, plus plain stats to cross-check it. "
             "Unreliable with little data: always mention uncertainty.",
             NoArgs, t_predict_weak_topic),
        Tool("get_similar_questions",
             "Real questions similar to a given question title (from our question database).",
             TitleArgs, t_get_similar_questions),
        Tool("predict_difficulty",
             "Predict Easy/Medium/Hard for a question using the difficulty classifier.",
             DifficultyArgs, t_predict_difficulty),
        Tool("search_problems",
             "Search the problem bank, optionally by topic/difficulty/status (status is for this student).",
             SearchProblemsArgs, t_search_problems),
        Tool("get_problem",
             "Get one problem's description plus this student's status, attempts and last code.",
             GetProblemArgs, t_get_problem),
        # Parts 4-6 add more tools here: get_hint, get_study_plan, ...
    ]
}


def _clean_schema(node):
    """Pydantic JSON schema -> simpler schema (no titles, Optional collapsed)."""
    if isinstance(node, dict):
        node = {k: _clean_schema(v) for k, v in node.items() if k != "title"}
        any_of = node.get("anyOf")
        if any_of:
            non_null = [x for x in any_of if x.get("type") != "null"]
            if len(non_null) == 1:
                merged = {k: v for k, v in node.items() if k != "anyOf"}
                merged.update(non_null[0])
                return merged
        return node
    if isinstance(node, list):
        return [_clean_schema(x) for x in node]
    return node


def tool_schemas() -> List[dict]:
    """OpenAI-style `tools` list for the Groq API. Note: no user_id anywhere."""
    out = []
    for t in TOOLS.values():
        params = _clean_schema(t.args_model.model_json_schema())
        params.pop("additionalProperties", None)
        out.append({
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": params},
        })
    return out


def _render(payload: dict) -> str:
    """JSON string for the model. Never longer than MAX_TOOL_OUTPUT_CHARS."""
    text = json.dumps(payload, default=str, ensure_ascii=False)
    if len(text) <= MAX_TOOL_OUTPUT_CHARS:
        return text
    cut = MAX_TOOL_OUTPUT_CHARS - 60          # room for the wrapper; escaping can add more, so re-check
    while True:
        out = json.dumps({"truncated": True, "partial_json": text[:cut]}, ensure_ascii=False)
        if len(out) <= MAX_TOOL_OUTPUT_CHARS or cut <= 0:
            return out
        cut = int(cut * 0.9)


def execute_tool(name: str, raw_arguments: Optional[str], ctx: ToolContext) -> tuple[bool, str]:
    """
    Run one tool call from the model. NEVER raises: problems come back as
    {"error": "..."} so the model can recover. Returns (ok, json_string).
    """
    tool = TOOLS.get(name)
    if not tool:
        return False, json.dumps({"error": f"Unknown tool '{name}'. Available: {sorted(TOOLS)}"})
    try:
        raw = json.loads(raw_arguments) if raw_arguments and raw_arguments.strip() else {}
        if not isinstance(raw, dict):
            raise ValueError("arguments must be a JSON object")
    except ValueError as e:
        return False, json.dumps({"error": f"Invalid JSON arguments: {e}"})
    try:
        args = tool.args_model.model_validate(raw)
    except ValidationError as e:
        problems = "; ".join(f"{'.'.join(map(str, err['loc'])) or 'arguments'}: {err['msg']}" for err in e.errors())
        return False, json.dumps({"error": f"Invalid arguments: {problems}"})
    try:
        result = tool.fn(ctx, args)
    except Exception as e:      # tool bugs must not crash the chat
        ctx.db.rollback()
        return False, json.dumps({"error": f"{type(e).__name__}: {e}"[:300]})
    return ("error" not in result), _render(result)
