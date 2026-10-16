"""
coach_router.py - /coach/* endpoints (chat, history, clear).
"""
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from agent.coach import CoachResult, build_user_message, get_client, run_coach
from agent.coach_tools import ToolContext
from models import CoachMessage, Problem, UserProblem, get_db

# CHANGE THIS ONE LINE: import the dependency from your Part 1 auth that returns the
# logged-in user's id. current_user.py is only a placeholder (reads an X-User-Id header).
# from current_user import get_user_id

from auth import get_current_user


def get_user_id(user=Depends(get_current_user)) -> int:
    """Logged-in user's id, from the Part 1 auth dependency."""
    if isinstance(user, int):
        return user
    if isinstance(user, dict):
        return int(user["id"])
    return int(user.id)

router = APIRouter(prefix="/coach", tags=["coach"])

MAX_MESSAGE_CHARS = 2000
MAX_CODE_CHARS = 8000
HISTORY_CONTEXT_MESSAGES = 20
RATE_LIMIT_PER_MINUTE = 20


# ── rate limit (per user, in memory: fine for one server process) ───────────
class RateLimiter:
    def __init__(self, limit: int, window_s: float = 60.0):
        self.limit = limit
        self.window_s = window_s
        self._hits: Dict[int, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, user_id: int) -> Optional[int]:
        """None if allowed, else seconds to wait."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[user_id]
            while hits and now - hits[0] >= self.window_s:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(1, int(self.window_s - (now - hits[0])) + 1)
            hits.append(now)
            return None


limiter = RateLimiter(RATE_LIMIT_PER_MINUTE)


# ── schemas ─────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(max_length=MAX_MESSAGE_CHARS)
    problem_id: Optional[int] = Field(default=None, ge=1)
    code: Optional[str] = Field(default=None, max_length=MAX_CODE_CHARS)   # unsaved editor text (optional)

    @field_validator("message")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty")
        return v


class ChatResponse(BaseModel):
    reply: str
    tools_used: List[str]
    steps: int
    limit_reached: bool = False


# ── helpers ─────────────────────────────────────────────────────────────────
def _is_visible(row: CoachMessage) -> bool:
    """user messages and FINAL assistant answers (not tool plumbing)."""
    if row.role == "user":
        return True
    return row.role == "assistant" and not (row.tool_calls or {}).get("calls") and bool(row.content)


def _load_history(db: Session, user_id: int, limit: int) -> List[CoachMessage]:
    rows = (
        db.query(CoachMessage)
        .filter(CoachMessage.user_id == user_id)
        .order_by(CoachMessage.id.desc())
        .limit(limit * 4)            # tool rows are skipped below
        .all()
    )
    visible = [r for r in reversed(rows) if _is_visible(r)][-limit:]
    while visible and visible[0].role != "user":    # context should start with a student message
        visible.pop(0)
    return visible


def _problem_context(db: Session, user_id: int, problem_id: int, code: Optional[str]) -> str:
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail="Problem not found")
    up = (
        db.query(UserProblem)
        .filter(UserProblem.user_id == user_id, UserProblem.problem_id == p.id)
        .first()
    )
    snippet = code if code else (up.last_code if up and up.last_code else "")
    lines = [
        f"The student is currently on this problem: {p.title} ({p.difficulty}; topics: {', '.join(p.topics or [])})",
        f"Problem statement: {(p.description or '')[:1500]}",
        f"Student's status: {up.status if up else 'todo'}; attempts: {up.attempts_count if up else 0}; hints used: {up.hints_used if up else 0}",
        f"Student's current code:\n{snippet[:2000]}" if snippet else "Student has not written any code yet.",
    ]
    return "\n".join(lines)


def _rows_for_turn(user_id: int, message: str, result: CoachResult) -> List[CoachMessage]:
    """DB rows for one chat turn: user, [tool requests, tool results], final answer."""
    rows = [CoachMessage(user_id=user_id, role="user", content=message)]
    last = len(result.new_messages) - 1
    for i, m in enumerate(result.new_messages):
        if m["role"] == "assistant" and "tool_calls" in m:
            rows.append(CoachMessage(user_id=user_id, role="assistant", content=m.get("content") or "",
                                     tool_calls={"calls": m["tool_calls"]}))
        elif m["role"] == "tool":
            rows.append(CoachMessage(user_id=user_id, role="tool", content=m["content"],
                                     tool_calls={"tool_call_id": m["tool_call_id"], "name": m["name"]}))
        elif m["role"] == "assistant" and i == last:
            rows.append(CoachMessage(user_id=user_id, role="assistant", content=m["content"],
                                     tool_calls={"tools_used": result.tools_used, "steps": result.steps}))
    return rows


# ── endpoints ───────────────────────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id),
):
    client = get_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Coach is unavailable: GROQ_API_KEY is not set on the server. Add it to backend/.env and restart.",
        )

    wait = limiter.check(user_id)
    if wait is not None:
        raise HTTPException(
            status_code=429,
            detail=f"Too many messages. Please wait {wait}s and try again.",
            headers={"Retry-After": str(wait)},
        )

    context = _problem_context(db, user_id, body.problem_id, body.code) if body.problem_id else None
    history = [{"role": r.role, "content": r.content}
               for r in _load_history(db, user_id, HISTORY_CONTEXT_MESSAGES)]

    try:
        result = run_coach(
            client,
            ToolContext(db=db, user_id=user_id),     # user_id comes from auth, never from the request body
            history,
            build_user_message(body.message, context),
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"Coach model call failed: {str(e)[:200]}")

    db.add_all(_rows_for_turn(user_id, body.message, result))
    db.commit()
    return ChatResponse(reply=result.reply, tools_used=result.tools_used,
                        steps=result.steps, limit_reached=result.limit_reached)


@router.get("/history")
def get_history(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id),
):
    rows = _load_history(db, user_id, limit)
    return {
        "messages": [
            {
                "id": r.id,
                "role": r.role,
                "content": r.content,
                "tools_used": (r.tool_calls or {}).get("tools_used", []) if r.role == "assistant" else [],
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    }


@router.delete("/history")
def clear_history(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_user_id),
):
    deleted = db.query(CoachMessage).filter(CoachMessage.user_id == user_id).delete()
    db.commit()
    return {"deleted": deleted}
