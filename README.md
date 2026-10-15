

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
| `/attempts/{user_id}` | GET | User attempt history (**login required**, own id only) |
| `/topic-stats/{user_id}` | GET | Per-topic solved counts (**login required**, own id only) |
| `/auth/signup` | POST | Create account `{email, password, name}` (or `first_name` + `last_name`) → `{access_token, user}` |
| `/auth/login` | POST | `{email, password}` → `{access_token, user}` |
| `/auth/me` | GET | Current user (Bearer token) |

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

## Authentication (Part 1)

Email + password accounts with JWT bearer tokens (HS256, 7-day expiry). Passwords are hashed with **argon2** and never stored or logged in plain text. User identity always comes from the verified token, never from the request.

- `POST /auth/signup`, `POST /auth/login`, `GET /auth/me` (see table above). Signup requires a name; the frontend sends `first_name`, `last_name` and a combined `name`. Passwords: min 8 characters. Login failures always return `Invalid email or password`.
- `/auth/signup` and `/auth/login` are rate limited (default `10/minute` per IP, in-memory, per server process).
- **Protected existing endpoints:** `/analyze`, `/attempts/{user_id}`, `/topic-stats/{user_id}`, `/progress/{user_id}` need `Authorization: Bearer <token>`. The old URL shapes still work, but the `{user_id}` must equal the logged-in user's id, otherwise **403**. The `user_id` field in the `/analyze` body is ignored. `/predict`, `/predict-difficulty`, `/recommend`, `/score`, `/model-evaluation`, `/dataset-stats` stay public.
- **Frontend:** `/login` and `/signup` are public; every other page requires login. The token is kept in `localStorage`, attached by the axios instance in `src/api.js`, and a 401 sends the user back to `/login`.

### Environment variables

Copy `backend/.env.example` to `backend/.env` (and `frontend/.env.example` to `frontend/.env.local`). Never commit real values.

| Variable | Where | Notes |
|----------|-------|-------|
| `DATABASE_URL` | backend | Falls back to `postgresql://postgres:password@localhost/coding_coach`. For Neon use its connection string; `sslmode=require` is added automatically for remote hosts. |
| `JWT_SECRET` | backend | **Required**, 32+ random chars: `python -c "import secrets; print(secrets.token_urlsafe(48))"`. If missing, only `/auth/*` returns 503; the rest of the API keeps working. |
| `GROQ_API_KEY` | backend | As before. |
| `CORS_ORIGINS` | backend | Optional, comma-separated, e.g. your Vercel URL. Empty = allow all (previous behaviour). |
| `AUTH_RATE_LIMIT` | backend | Optional, default `10/minute`. |
| `TRUSTED_PROXY_HOPS` | backend | Optional. Behind Render's proxy set to `1` so each client gets its own rate-limit bucket (0 = ignore `X-Forwarded-For`). Verify on your deployment. |
| `DEMO_PASSWORD` (+ `DEMO_EMAIL`, `DEMO_NAME`) | backend | Only read by `seed_demo_user.py`. |
| `VITE_API_URL` | frontend | Backend base URL. Baked in at build time: redeploy Vercel after changing it. |

### Database migrations (Alembic)

Schema changes go through Alembic only (`backend/alembic/`). Migration `0001_auth_foundation` is additive and idempotent: it adds nullable `password_hash`, `name`, `first_name`, `last_name`, `timezone` columns to the existing `users` table plus a unique index on `lower(email)`. Nothing is dropped or rewritten; existing tables are untouched.

```bash
cd backend
alembic upgrade head          # run against Neon BEFORE deploying the new backend
alembic current               # shows 0001_auth_foundation (head)
```

For Neon, prefer the **direct** (non-pooled) connection string for running migrations.

### Demo user (keeps the old `user_id=1` data visible)

```bash
cd backend
DEMO_PASSWORD='choose-a-password' python seed_demo_user.py
# log in with demo@example.com (or DEMO_EMAIL) and that password
```
It creates user id 1 if missing, never overwrites an existing password (use `--reset-password` to change it), and fixes the Postgres id sequence.

### Deploying (Render + Vercel + Neon)

1. Run `alembic upgrade head` (and the seed script if you want the demo user) against your Neon `DATABASE_URL` from your machine.
2. Render (backend): add `DATABASE_URL`, `JWT_SECRET`, `GROQ_API_KEY`, `CORS_ORIGINS` (your Vercel URL) and `TRUSTED_PROXY_HOPS=1`.
3. Vercel (frontend): set `VITE_API_URL` to the Render URL and redeploy.

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
export JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
docker-compose up --build
# then, once, to add the auth columns:
docker-compose exec backend alembic upgrade head
```

##  Testing

```bash
cd backend
pytest -v
```
ML tests (readiness score, weak-topic prediction) plus `tests/test_auth.py` (signup, login, token handling, rate limiting, per-user data isolation and 403s, demo seed). Auth tests run on an in-memory SQLite DB and never touch a real database.

##  Limitations & Future Work

- **Synthetic vs real data gap:** The weak-topic model achieves F1-macro=0.944 on a mixed train/test split (630 samples: 30 real + 600 synthetic), but only F1-macro=0.333 (XGBoost) when evaluated exclusively on the 30 real users. This indicates the model currently learns synthetic data patterns well but does not yet generalize strongly to real-world data. **Root cause:** 30 real samples is too small a holdout to be statistically reliable, and synthetic data was generated with artificially clean class separability. **Next step:** scale real data collection to 200+ users via the scraper, and re-run the real-only holdout at that scale.
- **Difficulty classifier:** TF-IDF + Logistic Regression (with `related_topics` and class balancing) achieves F1-weighted=0.487, F1-macro=0.47. Future improvement: replace TF-IDF with sentence embeddings (reusing the existing `all-MiniLM-L6-v2` model from the recommender) for richer semantic features.
- **Demo progress data:** `/progress/{user_id}` still seeds fake demo history for any user who has fewer than 2 weeks of real attempts (existing behaviour, not yet changed). Authentication and per-user data isolation are implemented (Part 1).


> Deployment in progress — run locally via Docker or Quick Start below.  



##  Built By

Samiksha Rana — [@SamikshaRana28](https://github.com/SamikshaRana28)