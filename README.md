

#  AI Coding Interview Coach

An intelligent coding interview preparation platform that combines AI-powered code review, ML-based weak-topic prediction, and NLP-driven question recommendations.

##  What It Does

Given your LeetCode solving history, this platform:
- Predicts which DSA topic you're weakest in (ML classification)
- Recommends similar practice questions (NLP/semantic search)
- Reviews your code for time/space complexity, bugs, and better approaches (LLM)
- Predicts difficulty of any question (NLP classification)
- Calculates an "Interview Readiness Score" (0-100)
- Tracks your progress over time

##  Tech Stack

**Backend:** FastAPI, Python, PostgreSQL, SQLAlchemy
**ML:** Scikit-learn, XGBoost, Sentence Transformers
**AI:** Groq API (LLaMA 3.3 70B)
**Frontend:** React, Vite, Tailwind CSS, Recharts, Monaco Editor
**Infra:** Docker, GitHub Codespaces

##  API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analyze` | POST | AI code review — complexity, bugs, better approach |
| `/predict` | POST | Predicts weakest DSA topic (XGBoost) |
| `/predict-difficulty` | POST | Predicts question difficulty (Easy/Medium/Hard) |
| `/recommend` | POST | Top 3 similar questions (NLP cosine similarity) |
| `/score` | POST | Interview Readiness Score (0-100) |
| `/model-evaluation` | GET | XGBoost vs Random Forest metrics |
| `/progress/{user_id}` | GET | Weekly score history |
| `/dataset-stats` | GET | Real LeetCode user data stats |
| `/attempts/{user_id}` | GET | User attempt history |
| `/problems` | GET | Question bank: `search`, `difficulty`, `topic`, `status`, `page`, `page_size` (status is per user) |
| `/problems/{id}` | GET | One problem + your status, `last_code`, `hints_used` |
| `/problems/{id}/submit` | POST | `{code, language}` → AI review, saves code, updates status (solved when no bugs) |
| `/problems/{id}/mark-solved` | POST | Manual "I solved it" (problems solved elsewhere) |
| `/admin/problems` | POST | Add one custom problem (needs `ADMIN_TOKEN`, see below) |

##  Problems (question bank)

The **Problems** tab lists the 500 questions the recommender already uses. Open one, solve it in the Monaco editor, hit **Submit** and get the same AI review as the Code Analyzer. Status (todo / attempted / solved) is tracked per user, and every submission also updates the existing `attempts` and `topic_progress` rows, so Topic Tracker, Dashboard and Progress stay in sync. The free-form Code Analyzer is unchanged.

**Set up the tables and data** (from `backend/`, with `DATABASE_URL` set):
```bash
alembic upgrade head                 # creates `problems` and `user_problems`
python -m scripts.seed_problems      # loads the 500 questions; safe to re-run (keyed by slug)
```
With Docker the migration runs on container start; seed with
`docker-compose exec backend python -m scripts.seed_problems` (`./data` is mounted at `/data`).

**Topics.** LeetCode's topic names are mapped to the app's: `arrays, dp, graphs, trees, strings, math, others` (`backend/problem_utils.py`). The first topic in a problem's list is its *primary topic*; that is the one a submission counts towards in Topic Tracker. DFS/BFS only mean "graphs" when the problem is not a tree problem; things like Hash Table, Linked List or Backtracking fall under `others` unless nothing else applies.

**How status works.** A submission whose review says `No bugs found` marks the problem **solved**; any other submission marks it **attempted**. Solved never goes back down, and a problem adds to the Topic Tracker solved count once, however many times you re-submit. "I solved it" marks a problem solved manually and counts it as one accepted attempt in Topic Tracker.

**Add your own question** (two equivalent ways):
```bash
# CLI, from backend/
python -m scripts.add_problem --title "Reverse Words" --difficulty Easy \
    --topics "strings,arrays" --description-file ./question.txt

# HTTP: set ADMIN_TOKEN on the server first (the endpoint is disabled without it)
curl -X POST http://localhost:8000/admin/problems \
  -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Reverse Words","difficulty":"Easy","topics":["strings"],"description":"..."}'
```
Custom problems get `source = "custom"` and are never overwritten by the seed script.

**No login yet.** "Per user" means the `X-User-Id` request header (default `1`, like the rest of the app). Real auth only needs to replace `current_user_id` in `backend/routers/problems.py`.

##  ML Models

### 1. Weak Topic Predictor — XGBoost vs Random Forest
- **Data:** 30 real scraped LeetCode profiles + 600 synthetic samples (630 total)
- **Features:** problem counts per topic, avg_attempts, acceptance_rate
- **Results (mixed train/test split):**
  - **XGBoost (winner):** F1-macro 0.944, ROC-AUC 0.999, CV F1 0.954±0.016
  - **Random Forest:** F1-macro 0.933, ROC-AUC 0.998, CV F1 0.920±0.019
- **Real-data-only holdout (30 real users, no synthetic):**
  - XGBoost F1-macro: 0.333
  - Random Forest F1-macro: 0.275
  - *(see Limitations below)*

### 2. Difficulty Classifier (NLP)
- TF-IDF (title + description + related_topics) + Logistic Regression with `class_weight="balanced"`
- **Results:** Accuracy 0.479, F1-weighted 0.487, F1-macro 0.47
- Per-class F1: Easy 0.43, Medium 0.53, Hard 0.44
- Output: Easy/Medium/Hard with confidence scores

### 3. Similar Questions Recommender (NLP)
- Sentence Transformers (`all-MiniLM-L6-v2`) + cosine similarity
- 500-question LeetCode dataset

### 4. Interview Readiness Score
- Weighted formula: Volume (30) + Variety (25) + Acceptance (25) + Efficiency (20)

##  Project Structure
ai-coding-coach/

├── backend/

│   ├── main.py

│   ├── models.py

│   ├── scrape_leetcode.py

│   ├── Dockerfile

│   ├── tests/

│   │   └── test_ml.py

│   └── ml/

│       ├── train_models.py

│       ├── difficulty_classifier.py

│       ├── predict.py

│       ├── recommender.py

│       ├── score.py

│       ├── progress.py

│       └── models/

├── data/

├── docker-compose.yml

└── frontend/

├── Dockerfile

└── src/

├── pages/

│   ├── ModelEvaluation.jsx

│   ├── CodeAnalyzer.jsx

│   ├── Dashboard.jsx

│   ├── SimilarQuestions.jsx

│   ├── TopicTracker.jsx

│   └── Progress.jsx

└── api.js
##  Quick Start

### Local Development
```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
python -m scripts.seed_problems
uvicorn main:app --port 8000 --reload

# Train ML models
python ml/train_models.py
python ml/difficulty_classifier.py

# Scrape real data (optional)
python scrape_leetcode.py

# Run tests
pytest -v

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

### Docker (all services)
```bash
export GROQ_API_KEY=your_key_here
docker-compose up --build
docker-compose exec backend python -m scripts.seed_problems   # first run only
```

##  Testing

```bash
cd backend
pytest -v
```
Covers readiness score and weak-topic prediction, plus the Problems feature: topic mapping, seed idempotency, list filters and pagination, submit/mark-solved status rules, the legacy `Attempt`/`TopicProgress` updates, and the admin endpoint (the LLM is faked, the DB is in-memory SQLite).

##  Limitations & Future Work

- **Synthetic vs real data gap:** The weak-topic model achieves F1-macro=0.944 on a mixed train/test split (630 samples: 30 real + 600 synthetic), but only F1-macro=0.333 (XGBoost) when evaluated exclusively on the 30 real users. This indicates the model currently learns synthetic data patterns well but does not yet generalize strongly to real-world data. **Root cause:** 30 real samples is too small a holdout to be statistically reliable, and synthetic data was generated with artificially clean class separability. **Next step:** scale real data collection to 200+ users via the scraper, and re-run the real-only holdout at that scale.
- **Difficulty classifier:** TF-IDF + Logistic Regression (with `related_topics` and class balancing) achieves F1-weighted=0.487, F1-macro=0.47. Future improvement: replace TF-IDF with sentence embeddings (reusing the existing `all-MiniLM-L6-v2` model from the recommender) for richer semantic features.
- **Single-user demo data** for progress tracking — multi-user authentication not implemented.


> Deployment in progress — run locally via Docker or Quick Start below.  



##  Built By

Samiksha Rana — [@SamikshaRana28](https://github.com/SamikshaRana28)