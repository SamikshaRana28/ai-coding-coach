import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agent.interviewer import MAX_USER_TURNS, run_agent_step, visible_history
from agent.tools import load_questions
from auth import get_current_user
from models import InterviewSession, User, WeakPattern, get_db

router = APIRouter()


class StartRequest(BaseModel):
    # user_id is NOT accepted from the client: identity comes from the token.
    topic: str = "arrays"


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)


def _get_session(db: Session, session_id: int, user: User) -> InterviewSession:
    s = db.get(InterviewSession, session_id)
    # Someone else's session looks exactly like a missing one (no id probing).
    if not s or s.user_id != user.id:
        raise HTTPException(404, "Interview session not found")
    return s


def _run(db, session, text, count_turn=True):
    try:
        return run_agent_step(db, session, text, count_turn=count_turn)
    except RuntimeError as e:                      # GROQ_API_KEY missing
        raise HTTPException(503, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(502, f"Interviewer agent error: {type(e).__name__}: {e}")


@router.get("/interview/topics")
def interview_topics(current_user: User = Depends(get_current_user)):
    return {"topics": sorted({q["topic"] for q in load_questions()})}


@router.post("/interview/start")
def start_interview(req: StartRequest, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    session = InterviewSession(user_id=current_user.id, topic=req.topic.strip().lower()[:50])
    db.add(session)
    db.commit()
    db.refresh(session)
    out = _run(db, session, f"Please start the interview. Preferred topic: {session.topic}.", count_turn=False)
    return {"session_id": session.id, "reply": out["reply"], "status": out["status"], "max_turns": MAX_USER_TURNS}


@router.post("/interview/{session_id}/answer")
def answer(session_id: int, req: AnswerRequest, db: Session = Depends(get_db),
           current_user: User = Depends(get_current_user)):
    session = _get_session(db, session_id, current_user)
    if session.status != "active":
        raise HTTPException(409, f"Interview is already {session.status}")
    out = _run(db, session, req.answer)
    return {"reply": out["reply"], "status": out["status"],
            "turns_used": session.step_count, "max_turns": MAX_USER_TURNS}


@router.get("/interview/{session_id}")
def get_interview(session_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    """Page reload / server restart ke baad UI yahin se chat wapas load karta hai."""
    s = _get_session(db, session_id, current_user)
    return {"session_id": s.id, "topic": s.topic, "status": s.status, "turns_used": s.step_count,
            "max_turns": MAX_USER_TURNS, "history": visible_history(db, s.id)}


@router.get("/interview/{session_id}/scorecard")
def get_scorecard(session_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    s = _get_session(db, session_id, current_user)
    if not s.scorecard:
        raise HTTPException(409, f"No scorecard yet (status: {s.status})")
    return json.loads(s.scorecard)


@router.get("/weak-patterns/{user_id}")
def weak_patterns(user_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    if user_id != current_user.id:
        raise HTTPException(403, "You can only access your own data")
    rows = db.query(WeakPattern).filter(WeakPattern.user_id == current_user.id).order_by(WeakPattern.count.desc()).all()
    return {"user_id": current_user.id, "weak_patterns": [{"pattern": r.pattern, "count": r.count, "source": r.source} for r in rows]}
