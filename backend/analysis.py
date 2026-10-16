"""
Shared AI-review logic.

Extracted from main.py's /analyze endpoint so that the free-form Code Analyzer
(/analyze) and the Problems page (/problems/{id}/submit) use ONE prompt and ONE
parser. Do not copy the prompt anywhere else - call run_analysis().
"""
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import HTTPException
from groq import Groq
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ml.rag_context import build_similar_questions_context
from models import Attempt, TopicProgress

load_dotenv()

# Groq doesn't crash the app if the key is missing; the endpoints return 503 instead.
groq_api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=groq_api_key) if groq_api_key else None

MODEL = "openai/gpt-oss-120b"
MAX_STATEMENT_CHARS = 4000


class AnalyzeResponse(BaseModel):
    time_complexity: str
    space_complexity: str
    bugs: str
    better_approach: str
    similar_questions: str
    interviewer_questions: str


def bugs_clean(bugs: Optional[str]) -> bool:
    """True when the review reports no bugs. Tolerates 'No bugs found.' / '**No bugs found**'."""
    normalized = (bugs or "").strip().strip("*_`\"' .!").lower()
    return normalized == "no bugs found"


def build_prompt(question: str, code: str, language: str,
                 retrieved_context: str, statement: Optional[str] = None) -> str:
    # `statement` is optional extra context (the Problems page passes the full problem
    # text). When it is None the prompt is exactly what /analyze always sent.
    statement_block = ""
    if statement and statement.strip():
        statement_block = "\nProblem statement:\n" + statement.strip()[:MAX_STATEMENT_CHARS]
    return f"""
You are a strict, expert coding interview coach reviewing a candidate's submission. Be critical and precise — do not assume the code is correct.

Problem: {question}{statement_block}
Code ({language}):
{code}

Here are real similar questions retrieved from our question database — use these, don't invent your own:
{retrieved_context}

IMPORTANT: First check if the code actually attempts to solve the stated problem. If the code is unrelated to the problem (e.g. solves a completely different algorithm), set BUGS to "MISMATCH: Code does not address the stated problem - it implements [what it actually does] instead", and set TIME_COMPLEXITY/SPACE_COMPLEXITY to the complexity of what the code DOES do (not "N/A").

If the code DOES attempt the stated problem, then check for syntax errors first (invalid statements, wrong punctuation, mismatched brackets) — report these in BUGS. Then check logic errors and edge cases.

Code ({language}):
{code}

First, check carefully for syntax errors (e.g. invalid statements, wrong punctuation like a semicolon in Python, mismatched brackets, indentation errors) — these would prevent the code from running at all. If there is a syntax error, that IS a bug and must be reported first.

Then check for logic errors, edge cases (empty input, no solution found, duplicates), and correctness vs the problem statement.

Reply in EXACTLY this format, one per line:

TIME_COMPLEXITY: [answer, or "N/A - syntax error" if code doesn't run]
SPACE_COMPLEXITY: [answer, or "N/A - syntax error" if code doesn't run]
BUGS: [list ALL bugs found, including syntax errors, with line references. If truly no bugs exist, write "No bugs found"]
BETTER_APPROACH: [better approach, or "This is optimal" only if code is correct and already optimal]
SIMILAR_QUESTIONS: [pick from the retrieved list above, explain briefly why each is similar]
INTERVIEWER_QUESTIONS: [3 interview questions]
"""


def parse_review(response_text: str) -> AnalyzeResponse:
    def extract(label):
        for line in response_text.split("\n"):
            if line.startswith(label + ":"):
                return line.replace(label + ":", "").strip()
        return "Not found"

    return AnalyzeResponse(
        time_complexity=extract("TIME_COMPLEXITY"),
        space_complexity=extract("SPACE_COMPLEXITY"),
        bugs=extract("BUGS"),
        better_approach=extract("BETTER_APPROACH"),
        similar_questions=extract("SIMILAR_QUESTIONS"),
        interviewer_questions=extract("INTERVIEWER_QUESTIONS"),
    )


def run_analysis(question: str, code: str, language: str = "python",
                 statement: Optional[str] = None) -> AnalyzeResponse:
    """Retrieve similar questions, call the LLM, parse the reply. Writes nothing to the DB."""
    if not client:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY .env mein set karo")

    try:
        retrieved_context = build_similar_questions_context(question)
        prompt = build_prompt(question, code, language, retrieved_context, statement)
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
        return parse_review(response.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def record_attempt(db: Session, *, user_id: int, question: str, code: str, topic: str,
                   difficulty: str, result: AnalyzeResponse,
                   count_solved: Optional[bool] = None) -> bool:
    """
    Add the Attempt row and update TopicProgress. Does NOT commit (caller does), so
    callers can fold more writes (e.g. user_problems) into the same transaction.

    count_solved: whether this submission adds to TopicProgress.count ("solved").
    Default (None) = whenever the review is clean, which is what /analyze always did.
    The Problems page passes False for re-solves so one problem counts once.
    Returns True if the review reported no bugs.
    """
    clean = bugs_clean(result.bugs)
    if count_solved is None:
        count_solved = clean

    db.add(Attempt(
        user_id=user_id,
        question=question,
        code=code,
        topic=topic,
        difficulty=difficulty,
        time_complexity=result.time_complexity,
        space_complexity=result.space_complexity,
        bugs_found=0 if clean else 1,
    ))

    tp = db.query(TopicProgress).filter(
        TopicProgress.user_id == user_id,
        TopicProgress.topic == topic,
    ).first()
    if tp:
        tp.total_attempts = (tp.total_attempts or 0) + 1
        if count_solved:
            tp.count = (tp.count or 0) + 1
    else:
        db.add(TopicProgress(
            user_id=user_id,
            topic=topic,
            count=1 if count_solved else 0,
            total_attempts=1,
        ))
    return clean
