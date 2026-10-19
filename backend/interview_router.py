import io
import json
import re
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from agent.delivery import DeliveryMetrics, delivery_report
from agent.interviewer import MAX_USER_TURNS, run_agent_step, visible_history
from agent.tools import load_questions
from auth import get_current_user
from models import InterviewSession, User, WeakPattern, get_db

router = APIRouter()


MAX_RESUME_BYTES = 3 * 1024 * 1024       # 3 MB PDF
MAX_RESUME_CHARS = 12000
MAX_RESUME_PAGES = 6


class StartRequest(BaseModel):
    # user_id is NOT accepted from the client: identity comes from the token.
    topic: str = "arrays"
    round: Literal["dsa", "behavioral", "sql", "resume", "mixed"] = "dsa"
    # Text from POST /interview/resume/extract (the server does not keep the PDF itself).
    resume_text: str | None = Field(default=None, max_length=MAX_RESUME_CHARS)


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=8000)


def _get_session(db: Session, session_id: int, user: User) -> InterviewSession:
    s = db.get(InterviewSession, session_id)
    # Someone else's session looks exactly like a missing one (no id probing).
    if not s or s.user_id != user.id:
        raise HTTPException(404, "Interview session not found")
    return s


def _wipe_resume_if_done(db: Session, session: InterviewSession) -> None:
    """Privacy: the resume text is only kept while the interview is running."""
    if session.status != "active" and session.resume_text:
        session.resume_text = None
        db.commit()


def _run(db, session, text, count_turn=True):
    try:
        out = run_agent_step(db, session, text, count_turn=count_turn)
        _wipe_resume_if_done(db, session)
        return out
    except RuntimeError as e:                      # GROQ_API_KEY missing
        raise HTTPException(503, str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(502, f"Interviewer agent error: {type(e).__name__}: {e}")


@router.get("/interview/topics")
def interview_topics(current_user: User = Depends(get_current_user)):
    return {"topics": sorted({q["topic"] for q in load_questions()})}


@router.post("/interview/resume/extract")
async def extract_resume(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """PDF -> plain text. Nothing is stored here: the browser sends the text back in /interview/start."""
    data = await file.read(MAX_RESUME_BYTES + 1)
    if len(data) > MAX_RESUME_BYTES:
        raise HTTPException(413, "Resume is too large (max 3 MB).")
    if not data.startswith(b"%PDF"):
        raise HTTPException(415, "Please upload a PDF file.")
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise HTTPException(422, "This PDF is password protected. Remove the password and try again.")
        pages = [(p.extract_text() or "") for p in reader.pages[:MAX_RESUME_PAGES]]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "Could not read this PDF. Try exporting it again from your editor.")
    text = re.sub(r"[ \t]+", " ", "\n".join(pages))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()[:MAX_RESUME_CHARS]
    if len(text) < 40:
        raise HTTPException(422, "No readable text found (scanned image PDFs are not supported).")
    return {"resume_text": text, "chars": len(text)}


@router.post("/interview/start")
def start_interview(req: StartRequest, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    resume = (req.resume_text or "").strip() or None
    if req.round == "resume" and not resume:
        raise HTTPException(422, "The resume round needs a resume. Upload a PDF first.")
    session = InterviewSession(user_id=current_user.id, topic=req.topic.strip().lower()[:50],
                               round=req.round, resume_text=resume if req.round in ("resume", "mixed") else None)
    db.add(session)
    db.commit()
    db.refresh(session)
    out = _run(db, session, f"Please start the interview. Round: {session.round}. Preferred topic: {session.topic}.",
               count_turn=False)
    return {"session_id": session.id, "round": session.round, "reply": out["reply"], "status": out["status"],
            "max_turns": MAX_USER_TURNS}


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
    return {"session_id": s.id, "topic": s.topic, "round": s.round or "dsa", "status": s.status,
            "turns_used": s.step_count, "max_turns": MAX_USER_TURNS, "has_resume": bool(s.resume_text),
            "history": visible_history(db, s.id)}


@router.delete("/interview/{session_id}/resume")
def delete_resume(session_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    s = _get_session(db, session_id, current_user)
    s.resume_text = None
    db.commit()
    return {"deleted": True}


@router.post("/interview/{session_id}/metrics")
def save_metrics(session_id: int, metrics: DeliveryMetrics, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """Aggregate delivery numbers computed IN THE BROWSER. Never video, images or landmarks."""
    s = _get_session(db, session_id, current_user)
    s.delivery_metrics = metrics.model_dump_json()
    db.commit()
    return {"saved": True}


@router.get("/interview/{session_id}/scorecard")
def get_scorecard(session_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    s = _get_session(db, session_id, current_user)
    if not s.scorecard:
        raise HTTPException(409, f"No scorecard yet (status: {s.status})")
    card = json.loads(s.scorecard)
    card.setdefault("round", s.round or "dsa")
    card["delivery"] = delivery_report(json.loads(s.delivery_metrics)) if s.delivery_metrics else None
    return card


@router.get("/weak-patterns/{user_id}")
def weak_patterns(user_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    if user_id != current_user.id:
        raise HTTPException(403, "You can only access your own data")
    rows = db.query(WeakPattern).filter(WeakPattern.user_id == current_user.id).order_by(WeakPattern.count.desc()).all()
    return {"user_id": current_user.id, "weak_patterns": [{"pattern": r.pattern, "count": r.count, "source": r.source} for r in rows]}
