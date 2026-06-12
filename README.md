# 🤖 AI Coding Interview Coach

An intelligent coding interview preparation platform powered by ML + NLP + AI.

## 🚀 Live Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analyze` | POST | AI code review — time/space complexity, bugs, approach |
| `/predict` | POST | Predicts your weakest DSA topic using ML |
| `/recommend` | POST | Top 3 similar LeetCode questions using NLP |
| `/score` | POST | Interview Readiness Score (0–100) |
| `/attempts/{user_id}` | GET | User attempt history |

## 🧠 ML Models Used

### 1. Weak Topic Predictor
- **Models:** Random Forest vs XGBoost (compared with cross-validation)
- **Features:** arrays_solved, graphs_solved, dp_solved, trees_solved, strings_solved, math_solved, avg_attempts, acceptance_rate
- **Result:** Random Forest F1-score: **0.705**
- **Labels:** arrays, dp, graphs, math, strings, trees

### 2. Similar Questions Recommender (NLP)
- **Model:** Sentence Transformers (`all-MiniLM-L6-v2`)
- **Technique:** Cosine similarity on question embeddings
- **Dataset:** LeetCode 500 questions
- **Output:** Top 3 semantically similar problems

### 3. Interview Readiness Score
- **Type:** Weighted formula (no training needed)
- **Components:** Volume (30pts) + Variety (25pts) + Acceptance Rate (25pts) + Efficiency (20pts)
- **Output:** Score 0–100 + level (Just Starting → Interview Ready 🔥)

## 🛠️ Tech Stack

**Backend:** FastAPI, Python, PostgreSQL, SQLAlchemy
**ML:** Scikit-learn, XGBoost, Sentence Transformers
**AI:** Groq API (LLaMA 3.3 70B)
**Frontend:** React
**Infra:** Docker, GitHub Codespaces

## 📁 Project Structure

```
ai-coding-coach/
├── backend/
│   ├── main.py          # FastAPI app + all endpoints
│   ├── models.py        # PostgreSQL schema
│   └── ml/
│       ├── train.py     # Model training script
│       ├── predict.py   # Weak topic predictor
│       ├── recommender.py # NLP similarity engine
│       └── score.py     # Readiness score calculator
├── data/
│   ├── user_data.csv         # Synthetic training data (1000 users)
│   └── leetcode_dataset.csv  # LeetCode problems dataset
└── frontend/
    └── src/App.jsx      # React UI
```

## ⚡ Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --port 8000 --reload

# Test predict endpoint
curl -X POST "http://localhost:8000/predict" \
-H "Content-Type: application/json" \
-d '{"arrays_solved":2,"graphs_solved":25,"dp_solved":20,
     "trees_solved":18,"strings_solved":15,"math_solved":12,
     "avg_attempts":3.5,"acceptance_rate":0.45}'
```

## 📊 Model Evaluation

| Model | F1-Score | CV Folds |
|-------|----------|----------|
| Random Forest | **0.705** | 5 |
| XGBoost | 0.695 | 5 |

## 👩‍💻 Built By

Samiksha Rana — [@SamikshaRana28](https://github.com/SamikshaRana28)