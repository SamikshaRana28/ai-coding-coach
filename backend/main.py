from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq
from sqlalchemy.orm import Session
from models import get_db, Attempt, create_tables
from ml.predict import predict_weak_topic
from ml.recommender import get_similar_questions
from ml.score import calculate_readiness_score
from ml.progress import get_or_generate_progress
import os
import json
from pathlib import Path
import joblib

load_dotenv()

app = FastAPI(title="AI Coding Coach")
create_tables()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ FIX: Groq crash nahi karega agar key missing ho
groq_api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=groq_api_key) if groq_api_key else None

MODELS_DIR = Path(__file__).parent / "ml" / "models"

DIFF_MODEL_PATH = MODELS_DIR / "difficulty_model.joblib"
DIFF_VEC_PATH = MODELS_DIR / "difficulty_vectorizer.joblib"

diff_model = joblib.load(DIFF_MODEL_PATH) if DIFF_MODEL_PATH.exists() else None
diff_vectorizer = joblib.load(DIFF_VEC_PATH) if DIFF_VEC_PATH.exists() else None


# ── Pydantic Models (same as before, kuch nahi badla) ──────────────────────
class AnalyzeRequest(BaseModel):
    question: str
    code: str
    language: str = "python"
    topic: str = "general"
    difficulty: str = "medium"
    user_id: int = 1

class AnalyzeResponse(BaseModel):
    time_complexity: str
    space_complexity: str
    bugs: str
    better_approach: str
    similar_questions: str
    interviewer_questions: str

class UserStats(BaseModel):
    arrays_solved: int
    graphs_solved: int
    dp_solved: int
    trees_solved: int
    strings_solved: int
    math_solved: int
    avg_attempts: float
    acceptance_rate: float
class DifficultyInput(BaseModel):
    title: str
    description: str = ""
class QuestionInput(BaseModel):
    title: str


# ── PURANE ENDPOINTS (bilkul same, kuch nahi badla) ────────────────────────
@app.get("/")
def root():
    return {"message": "AI Coding Coach API is running!", "version": "2.0"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_code(request: AnalyzeRequest, db: Session = Depends(get_db)):
    if not client:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY .env mein set karo")

    prompt = f"""
You are an expert coding interview coach. Analyze the following code.

Problem: {request.question}

Code ({request.language}):
{request.code}

Reply in EXACTLY this format, one per line:

TIME_COMPLEXITY: [answer]
SPACE_COMPLEXITY: [answer]
BUGS: [bugs or "No bugs found"]
BETTER_APPROACH: [better approach or "This is optimal"]
SIMILAR_QUESTIONS: [3 similar questions]
INTERVIEWER_QUESTIONS: [3 interview questions]
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
        )
        response_text = response.choices[0].message.content

        def extract(label):
            for line in response_text.split("\n"):
                if line.startswith(label + ":"):
                    return line.replace(label + ":", "").strip()
            return "Not found"

        result = AnalyzeResponse(
            time_complexity=extract("TIME_COMPLEXITY"),
            space_complexity=extract("SPACE_COMPLEXITY"),
            bugs=extract("BUGS"),
            better_approach=extract("BETTER_APPROACH"),
            similar_questions=extract("SIMILAR_QUESTIONS"),
            interviewer_questions=extract("INTERVIEWER_QUESTIONS"),
        )

        attempt = Attempt(
            user_id=request.user_id,
            question=request.question,
            code=request.code,
            topic=request.topic,
            difficulty=request.difficulty,
            time_complexity=result.time_complexity,
            space_complexity=result.space_complexity,
            bugs_found=0 if result.bugs == "No bugs found" else 1,
        )
        db.add(attempt)
        db.commit()
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/attempts/{user_id}")
def get_attempts(user_id: int, db: Session = Depends(get_db)):
    attempts = db.query(Attempt).filter(Attempt.user_id == user_id).all()
    return {"total": len(attempts), "attempts": [
        {
            "question": a.question,
            "topic": a.topic,
            "difficulty": a.difficulty,
            "time_complexity": a.time_complexity,
            "created_at": str(a.created_at)
        } for a in attempts
    ]}


@app.post("/predict")
def predict(stats: UserStats):
    return predict_weak_topic(
        stats.arrays_solved, stats.graphs_solved, stats.dp_solved,
        stats.trees_solved, stats.strings_solved, stats.math_solved,
        stats.avg_attempts, stats.acceptance_rate
    )
@app.post("/predict-difficulty")
def predict_difficulty(data: DifficultyInput):
    if not diff_model or not diff_vectorizer:
        raise HTTPException(
            status_code=503,
            detail="Difficulty model not trained yet"
        )

    text = data.title + " " + data.description[:300]

    vec = diff_vectorizer.transform([text])

    pred = diff_model.predict(vec)[0]

    probs = diff_model.predict_proba(vec)[0]

    classes = diff_model.classes_

    return {
        "predicted_difficulty": pred,
        "confidence": round(float(max(probs)), 3),
        "all_probabilities": {
            c: round(float(p), 3)
            for c, p in zip(classes, probs)
        }
    }

@app.post("/recommend")
def recommend(data: QuestionInput):
    return {"similar_questions": get_similar_questions(data.title)}


@app.post("/score")
def get_score(stats: UserStats):
    return calculate_readiness_score(
        stats.arrays_solved, stats.graphs_solved, stats.dp_solved,
        stats.trees_solved, stats.strings_solved, stats.math_solved,
        stats.avg_attempts, stats.acceptance_rate
    )


# ── NAAYE ENDPOINTS (3 naye features) ─────────────────────────────────────

@app.get("/model-evaluation")
def get_model_evaluation():
    """
    XGBoost vs Random Forest A/B comparison metrics.
    ml/train_models.py chalane ke baad real data aata hai.
    Pehle demo data dikhata hai.
    """
    eval_path = MODELS_DIR / "evaluation.json"

    if eval_path.exists():
        with open(eval_path) as f:
            return json.load(f)

    # Demo fallback — train_models.py chalane se pehle
    return {
        "trained_at": "demo - run: python ml/train_models.py",
        "data_source": "synthetic",
        "dataset_size": 700,
        "winner": "XGBoost",
        "xgboost": {
            "accuracy": 0.8714,
            "f1_macro": 0.8691,
            "f1_weighted": 0.8703,
            "roc_auc": 0.9612,
            "cv_f1_mean": 0.8534,
            "cv_f1_std": 0.0213,
            "confusion_matrix": [
                [45,2,1,0,1,1],[2,43,1,2,1,1],[1,2,44,1,1,1],
                [0,1,2,46,0,1],[1,1,1,0,45,2],[0,2,1,1,1,45]
            ],
            "class_labels": ["arrays","dp","graphs","math","strings","trees"],
            "per_class_f1": {
                "arrays":0.902,"dp":0.871,"graphs":0.880,
                "math":0.921,"strings":0.893,"trees":0.875
            },
            "feature_importance": {
                "arrays_solved":0.198,"graphs_solved":0.167,"dp_solved":0.189,
                "trees_solved":0.142,"strings_solved":0.156,"math_solved":0.081,
                "avg_attempts":0.038,"acceptance_rate":0.029
            }
        },
        "random_forest": {
            "accuracy": 0.8429,
            "f1_macro": 0.8401,
            "f1_weighted": 0.8415,
            "roc_auc": 0.9388,
            "cv_f1_mean": 0.8214,
            "cv_f1_std": 0.0287,
            "confusion_matrix": [
                [43,2,2,1,1,1],[3,41,2,2,1,1],[2,2,42,2,1,1],
                [1,2,2,44,0,1],[1,2,2,0,43,2],[1,2,2,1,2,42]
            ],
            "class_labels": ["arrays","dp","graphs","math","strings","trees"],
            "per_class_f1": {
                "arrays":0.875,"dp":0.841,"graphs":0.851,
                "math":0.898,"strings":0.862,"trees":0.840
            },
            "feature_importance": {
                "arrays_solved":0.187,"graphs_solved":0.159,"dp_solved":0.176,
                "trees_solved":0.139,"strings_solved":0.148,"math_solved":0.093,
                "avg_attempts":0.055,"acceptance_rate":0.043
            }
        },
        "feature_cols": [
            "arrays_solved","graphs_solved","dp_solved",
            "trees_solved","strings_solved","math_solved",
            "avg_attempts","acceptance_rate"
        ],
        "class_labels": ["arrays","dp","graphs","math","strings","trees"]
    }


@app.get("/progress/{user_id}")
def get_progress(user_id: int, db: Session = Depends(get_db)):
    """
    Weekly readiness score progression.
    Real attempts se calculate karta hai, warna demo data dikhata hai.
    """
    progress = get_or_generate_progress(user_id, db)
    return {"user_id": user_id, "weeks": len(progress), "progress": progress}


@app.get("/dataset-stats")
def get_dataset_stats(db: Session = Depends(get_db)):
    """
    Kitne real LeetCode users scrape kiye — Model Eval page ke liye.
    """
    try:
        from sqlalchemy import text
        count = db.execute(text("SELECT COUNT(*) FROM leetcode_users")).scalar()
        avg = db.execute(text("SELECT AVG(total_solved) FROM leetcode_users")).scalar()
        return {
            "real_users_scraped": int(count or 0),
            "avg_problems_solved": round(float(avg or 0), 1),
            "source": "LeetCode GraphQL API (public)",
        }
    except Exception:
        return {
            "real_users_scraped": 0,
            "avg_problems_solved": 0,
            "source": "scrape_leetcode.py chalao pehle",
        }