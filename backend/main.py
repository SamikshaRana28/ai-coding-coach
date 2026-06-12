# # from fastapi import FastAPI, HTTPException
# # from fastapi.middleware.cors import CORSMiddleware
# # from pydantic import BaseModel
# # from dotenv import load_dotenv
# # from groq import Groq
# # import os

# # load_dotenv()

# # app = FastAPI(title="AI Coding Coach")

# # app.add_middleware(
# #     CORSMiddleware,
# #     allow_origins=["*"],
# #     allow_methods=["*"],
# #     allow_headers=["*"],
# # )

# # client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# # class AnalyzeRequest(BaseModel):
# #     question: str
# #     code: str
# #     language: str = "python"

# # class AnalyzeResponse(BaseModel):
# #     time_complexity: str
# #     space_complexity: str
# #     bugs: str
# #     better_approach: str
# #     similar_questions: str
# #     interviewer_questions: str

# # @app.get("/")
# # def root():
# #     return {"message": "AI Coding Coach API is running!"}

# # @app.post("/analyze", response_model=AnalyzeResponse)
# # def analyze_code(request: AnalyzeRequest):
# #     prompt = f"""
# # You are an expert coding interview coach. Analyze the following code.

# # Problem: {request.question}

# # Code ({request.language}):
# # {request.code}

# # Reply in EXACTLY this format, one per line:

# # TIME_COMPLEXITY: [answer]
# # SPACE_COMPLEXITY: [answer]
# # BUGS: [bugs or "No bugs found"]
# # BETTER_APPROACH: [better approach or "This is optimal"]
# # SIMILAR_QUESTIONS: [3 similar questions]
# # INTERVIEWER_QUESTIONS: [3 interview questions]
# # """

# #     try:
# #         response = client.chat.completions.create(
# #             model="llama-3.3-70b-versatile",
# #             messages=[{"role": "user", "content": prompt}],
# #             max_tokens=1000,
# #         )

# #         response_text = response.choices[0].message.content

# #         def extract(label):
# #             for line in response_text.split("\n"):
# #                 if line.startswith(label + ":"):
# #                     return line.replace(label + ":", "").strip()
# #             return "Not found"

# #         return AnalyzeResponse(
# #             time_complexity=extract("TIME_COMPLEXITY"),
# #             space_complexity=extract("SPACE_COMPLEXITY"),
# #             bugs=extract("BUGS"),
# #             better_approach=extract("BETTER_APPROACH"),
# #             similar_questions=extract("SIMILAR_QUESTIONS"),
# #             interviewer_questions=extract("INTERVIEWER_QUESTIONS"),
# #         )

# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=str(e))













# from fastapi import FastAPI, HTTPException, Depends
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from dotenv import load_dotenv
# from groq import Groq
# from sqlalchemy.orm import Session
# from models import get_db, Attempt, create_tables
# import os

# load_dotenv()

# app = FastAPI(title="AI Coding Coach")

# create_tables()

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# class AnalyzeRequest(BaseModel):
#     question: str
#     code: str
#     language: str = "python"
#     topic: str = "general"
#     difficulty: str = "medium"
#     user_id: int = 1

# class AnalyzeResponse(BaseModel):
#     time_complexity: str
#     space_complexity: str
#     bugs: str
#     better_approach: str
#     similar_questions: str
#     interviewer_questions: str

# @app.get("/")
# def root():
#     return {"message": "AI Coding Coach API is running!"}

# @app.post("/analyze", response_model=AnalyzeResponse)
# def analyze_code(request: AnalyzeRequest, db: Session = Depends(get_db)):
#     prompt = f"""
# You are an expert coding interview coach. Analyze the following code.

# Problem: {request.question}

# Code ({request.language}):
# {request.code}

# Reply in EXACTLY this format, one per line:

# TIME_COMPLEXITY: [answer]
# SPACE_COMPLEXITY: [answer]
# BUGS: [bugs or "No bugs found"]
# BETTER_APPROACH: [better approach or "This is optimal"]
# SIMILAR_QUESTIONS: [3 similar questions]
# INTERVIEWER_QUESTIONS: [3 interview questions]
# """

#     try:
#         response = client.chat.completions.create(
#             model="llama-3.3-70b-versatile",
#             messages=[{"role": "user", "content": prompt}],
#             max_tokens=1000,
#         )

#         response_text = response.choices[0].message.content

#         def extract(label):
#             for line in response_text.split("\n"):
#                 if line.startswith(label + ":"):
#                     return line.replace(label + ":", "").strip()
#             return "Not found"

#         result = AnalyzeResponse(
#             time_complexity=extract("TIME_COMPLEXITY"),
#             space_complexity=extract("SPACE_COMPLEXITY"),
#             bugs=extract("BUGS"),
#             better_approach=extract("BETTER_APPROACH"),
#             similar_questions=extract("SIMILAR_QUESTIONS"),
#             interviewer_questions=extract("INTERVIEWER_QUESTIONS"),
#         )

#         # Database mein save karo
#         attempt = Attempt(
#             user_id=request.user_id,
#             question=request.question,
#             code=request.code,
#             topic=request.topic,
#             difficulty=request.difficulty,
#             time_complexity=result.time_complexity,
#             space_complexity=result.space_complexity,
#             bugs_found=0 if result.bugs == "No bugs found" else 1,
#         )
#         db.add(attempt)
#         db.commit()

#         return result

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/attempts/{user_id}")
# def get_attempts(user_id: int, db: Session = Depends(get_db)):
#     attempts = db.query(Attempt).filter(Attempt.user_id == user_id).all()
#     return {"total": len(attempts), "attempts": [
#         {
#             "question": a.question,
#             "topic": a.topic,
#             "difficulty": a.difficulty,
#             "time_complexity": a.time_complexity,
#             "created_at": str(a.created_at)
#         } for a in attempts
#     ]}
# # Yeh import upar add karo (baaki imports ke saath)
# from ml.predict import predict_weak_topic
# from pydantic import BaseModel

# # Yeh class add karo
# class UserStats(BaseModel):
#     arrays_solved: int
#     graphs_solved: int
#     dp_solved: int
#     trees_solved: int
#     strings_solved: int
#     math_solved: int
#     avg_attempts: float
#     acceptance_rate: float

# # Yeh endpoint add karo
# @app.post("/predict")
# def predict(stats: UserStats):
#     result = predict_weak_topic(
#         stats.arrays_solved,
#         stats.graphs_solved,
#         stats.dp_solved,
#         stats.trees_solved,
#         stats.strings_solved,
#         stats.math_solved,
#         stats.avg_attempts,
#         stats.acceptance_rate
#     )
#     return result
# # Yeh import upar add karo
# from ml.recommender import get_similar_questions

# # Yeh class add karo
# class QuestionInput(BaseModel):
#     title: str

# # Yeh endpoint add karo
# @app.post("/recommend")
# def recommend(data: QuestionInput):
#     results = get_similar_questions(data.title)
#     return {"similar_questions": results}
# # Import upar add karo
# from ml.score import calculate_readiness_score

# # Endpoint add karo
# @app.post("/score")
# def get_score(stats: UserStats):
#     result = calculate_readiness_score(
#         stats.arrays_solved,
#         stats.graphs_solved,
#         stats.dp_solved,
#         stats.trees_solved,
#         stats.strings_solved,
#         stats.math_solved,
#         stats.avg_attempts,
#         stats.acceptance_rate
#     )
#     return result















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
import os

load_dotenv()

app = FastAPI(title="AI Coding Coach")
create_tables()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Models ─────────────────────────────────────────
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

class QuestionInput(BaseModel):
    title: str

# ── Endpoints ──────────────────────────────────────
@app.get("/")
def root():
    return {"message": "AI Coding Coach API is running!"}

@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_code(request: AnalyzeRequest, db: Session = Depends(get_db)):
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