<!-- 

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

Samiksha Rana — [@SamikshaRana28](https://github.com/SamikshaRana28) -->











































































# AI Coding Interview Coach

An interview-prep platform that combines AI code review, a problem bank with per-user progress, a 3-level hint system, a tool-using Coach chat, an interviewer agent, and ML models (weak-topic prediction, difficulty prediction, similar-question search).

## What it does

- Login/signup with JWT; every per-user feature is tied to the logged-in user
- Problem bank (500 questions): solve in a Monaco editor, submit for an AI review, status tracked per user (todo / attempted / solved)
- **Hints (3 levels)** unlocked one at a time, only when you ask; never the full solution
- **Coach**: a chat agent (Groq tool calling) that reads your real stats, attempts and problems, and can unlock hints
- **Interviewer agent**: mock interview sessions with a scorecard and weak-pattern tracking
- ML: weak-topic predictor (XGBoost), difficulty classifier (TF-IDF + LR), similar questions (sentence embeddings)
- Interview Readiness Score (0-100) and weekly progress
- Dashboard with solved / solved-without-hints / hints-used cards

## Tech stack

**Backend:** FastAPI, Python 3.12, PostgreSQL, SQLAlchemy, Alembic, PyJWT, argon2, slowapi
**ML:** scikit-learn, XGBoost, fastembed (sentence embeddings)
**AI:** Groq API (chat completions with tool calling)
**Frontend:** React, Vite, Tailwind CSS, Monaco Editor, axios
**Infra:** Docker, GitHub Codespaces

## Authentication

Every per-user endpoint takes the user from the JWT (`Authorization: Bearer <token>`).

- `/problems*`, `/problem-stats`, `/analyze`, `/attempts/{user_id}`, `/topic-stats/{user_id}`, `/progress/{user_id}`, `/coach/*`, `/interview/*` all require login (401 otherwise).
- A `user_id` in the URL must match the token (otherwise 403). A `user_id` in a request body is ignored.
- The old `X-User-Id` header is **no longer read**.
- Login/signup are rate limited (`AUTH_RATE_LIMIT`, per client IP).
- Validation errors (422) never echo the submitted input back (so a rejected password is not returned).

## API endpoints

### Auth
| Endpoint | Method | Description |
|---|---|---|
| `/auth/signup` | POST | Create account, returns user + access token |
| `/auth/login` | POST | Returns user + access token |
| `/auth/me` | GET | Current user |

### Problems and hints
| Endpoint | Method | Description |
|---|---|---|
| `/problems` | GET | Question bank: `search`, `difficulty`, `topic`, `status`, `page`, `page_size` (status and `hints_used` are per user) |
| `/problems/{id}` | GET | One problem + your status, `last_code`, `hints_used`, the `hints` you already unlocked, `max_hint_level` |
| `/problems/{id}/submit` | POST | `{code, language}` → AI review, saves code, updates status (solved when no bugs) |
| `/problems/{id}/mark-solved` | POST | Manual "I solved it" |
| `/problems/{id}/hint` | POST | Next hint (level 1 → 3), only when asked. Body optional: `{level?, code?}` |
| `/problem-stats` | GET | Solved / attempted and how many solved problems needed no hint |
| `/admin/problems` | POST | Add one custom problem (needs `ADMIN_TOKEN`) |

### Analyzer, ML, progress
| Endpoint | Method | Description |
|---|---|---|
| `/analyze` | POST | AI code review (complexity, bugs, better approach); saved for the logged-in user |
| `/predict` | POST | Weakest DSA topic (XGBoost) |
| `/predict-difficulty` | POST | Easy/Medium/Hard from title + description |
| `/recommend` | POST | Similar questions (cosine similarity); each item has a nullable `problem_id` |
| `/score` | POST | Interview Readiness Score (0-100) |
| `/model-evaluation` | GET | XGBoost vs Random Forest metrics |
| `/progress/{user_id}` | GET | Weekly score history |
| `/topic-stats/{user_id}` | GET | Solved count per topic + acceptance rate |
| `/attempts/{user_id}` | GET | Attempt history |
| `/dataset-stats` | GET | Real LeetCode user data stats |

### Coach and interviewer
| Endpoint | Method | Description |
|---|---|---|
| `/coach/chat` | POST | Message (+ optional `problem_id`, `code`) → reply, `tools_used` |
| `/coach/history` | GET / DELETE | Stored conversation for the logged-in user |
| `/interview/topics` | GET | Available interview topics |
| `/interview/start` | POST | Start a mock interview |
| `/interview/{id}/answer` | POST | Send an answer |
| `/interview/{id}` | GET | Session state |
| `/interview/{id}/scorecard` | GET | Final scorecard |
| `/weak-patterns/{user_id}` | GET | Patterns flagged in interviews |

## Problems (question bank)

The **Problems** tab lists the 500 questions the recommender uses. Open one, solve it, hit **Submit** and get an AI review. Status is tracked per user, and each submission also updates the `attempts` and `topic_progress` rows, so Topic Tracker, Dashboard and Progress stay in sync.

**How status works.** A review that says `No bugs found` marks the problem **solved**; anything else marks it **attempted**. Solved never goes back down, and a problem counts once towards Topic Tracker however often you re-submit. "I solved it" marks it solved manually.

**Topics.** LeetCode topics are mapped to `arrays, dp, graphs, trees, strings, math, others` (`backend/problem_utils.py`). The first topic is the *primary topic* that a submission counts towards.

**Add your own question:**
```bash
# CLI, from backend/
python -m scripts.add_problem --title "Reverse Words" --difficulty Easy \
    --topics "strings,arrays" --description-file ./question.txt

# HTTP (endpoint is disabled unless ADMIN_TOKEN is set on the server)
curl -X POST http://localhost:8000/admin/problems \
  -H "X-Admin-Token: $ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Reverse Words","difficulty":"Easy","topics":["strings"],"description":"..."}'
```
Custom problems get `source = "custom"` and are never overwritten by the seed script.

## Hints

The **Hint** button unlocks one level per click, in order:

1. a small nudge
2. the approach in words
3. a pseudo-code outline (never the full solution)

- Generated by the LLM only when asked, with a guard against leaking a full solution.
- Stored in `hint_events` (one row per user, problem, level), so a repeat click or reopening the problem shows the same text with no new LLM call. Counted in `user_problems.hints_used`.
- LLM generations are rate limited per user (cached hints are free).
- The Coach has the same levels through its `get_hint` tool (it cannot skip levels).
- A small "Stuck?" nudge appears after 10 minutes on an unsolved problem. It only suggests.
- The Dashboard shows problems solved, solved without hints, and total hints used.

## Coach

A chat panel on the problem page ("Ask Coach about this problem"). The conversation is stored on the server per user. The Coach uses tools (`get_topic_stats`, `get_attempts`, `get_readiness_score`, `predict_weak_topic`, `get_similar_questions`, `predict_difficulty`, `search_problems`, `get_problem`, `get_hint`) and never receives a `user_id` argument: the server injects the logged-in user's id.

## ML models

1. **Weak-topic predictor** (XGBoost vs Random Forest): 30 real scraped profiles + 600 synthetic samples. Mixed split F1-macro 0.944 (XGBoost); real-only holdout F1-macro 0.333 (XGBoost), 0.275 (RF).
2. **Difficulty classifier**: TF-IDF + Logistic Regression, accuracy 0.479, F1-weighted 0.487.
3. **Similar questions**: sentence embeddings + cosine similarity over the 500-question dataset.
4. **Readiness score**: Volume (30) + Variety (25) + Acceptance (25) + Efficiency (20).

## Project structure

```
ai-coding-coach/
├── backend/
│   ├── main.py                 # app, legacy endpoints, auth-protected routes
│   ├── auth.py                 # signup/login/me, JWT, get_current_user, require_path_user
│   ├── models.py               # SQLAlchemy models (incl. HintEvent)
│   ├── hints.py                # hint service: levels, cache, LLM prompt, no-solution guard
│   ├── analysis.py             # LLM code review shared by /analyze and /submit
│   ├── coach_router.py         # /coach/* endpoints, RateLimiter
│   ├── interview_router.py     # /interview/* endpoints
│   ├── problems_service.py, problem_utils.py, user_stats.py
│   ├── routers/problems.py     # /problems*, /problem-stats, /admin/problems
│   ├── agent/                  # coach.py (agent loop), coach_tools.py (tools), tools.py
│   ├── ml/                     # training, predict, recommender, score, progress
│   ├── alembic/versions/       # 0001_auth_foundation → 0001_problems → 0002 → 0003
│   ├── scripts/                # seed_problems.py, add_problem.py
│   └── tests/                  # conftest.py, test_problems.py, test_hints.py, test_auth.py, ...
├── data/
├── docker-compose.yml
└── frontend/src/
    ├── api.js                  # axios + JWT interceptor
    ├── auth/                   # useAuth, login/signup
    ├── components/             # HintPanel.jsx, CoachWidget.jsx, ReviewPanel, ProblemBits
    └── pages/                  # Dashboard, Problems, ProblemPage, CodeAnalyzer, ...
```

## Quick start (local / Codespaces)

Use **Python 3.12** (see `backend/runtime.txt`). Newer Python versions have no wheels for the pinned ML packages.

```bash
# Database (Postgres in Docker)
docker compose up -d db

# Backend
cd backend
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then edit: GROQ_API_KEY, JWT_SECRET, DATABASE_URL
alembic upgrade head            # users, problems, user_problems, coach_messages, hint_events
python -m scripts.seed_problems # 500 questions, safe to re-run
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

In Codespaces, set port 8000 to **Public** and put the forwarded URL in `frontend/.env` as `VITE_API_URL=https://<codespace>-8000.app.github.dev`.

**Migrations.** The chain must have one head: `alembic heads` should print only `0003`. If tables already exist from `create_tables()`, run `alembic stamp 0001_auth_foundation` first, then `alembic upgrade head`.

**Docker (all services):**
```bash
export GROQ_API_KEY=your_key_here
docker-compose up --build
docker-compose exec backend python -m scripts.seed_problems   # first run only
```

## Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres URL (SQLite works for tests; remote hosts get `sslmode=require` added) |
| `GROQ_API_KEY` | LLM access |
| `JWT_SECRET` | Required, 32+ random characters. Define it once |
| `JWT_EXPIRE_DAYS` | Token lifetime (default 7) |
| `CORS_ORIGINS` | Comma-separated allowed origins (empty = all) |
| `AUTH_RATE_LIMIT` | e.g. `10/minute` for login/signup |
| `RATE_LIMIT_ENABLED` | `false` only for tests/debugging |
| `TRUSTED_PROXY_HOPS` | Reverse proxies in front of the app |
| `ADMIN_TOKEN` | Enables `/admin/problems` |
| `DEMO_EMAIL`, `DEMO_NAME`, `DEMO_PASSWORD` | Used by `seed_demo_user.py` |

Never commit `.env` or paste it anywhere. If a key leaks, rotate it.

## Deployment

- **Frontend (Vercel):** https://ai-coding-coach-self.vercel.app/
- **Backend:** `<your backend URL>` (add it here; the env notes in this repo assume Render, with a Neon Postgres database)

Set these in the hosting dashboards, not in git:

| Where | Variable | Value |
|---|---|---|
| Vercel | `VITE_API_URL` | the public backend URL (redeploy the frontend after changing it) |
| Backend host | `DATABASE_URL` | the Neon/Postgres connection string |
| Backend host | `GROQ_API_KEY`, `JWT_SECRET` | secrets (`JWT_SECRET` 32+ random characters) |
| Backend host | `CORS_ORIGINS` | `https://ai-coding-coach-self.vercel.app` |
| Backend host | `TRUSTED_PROXY_HOPS` | `1` on Render |

**After deploying the hints/auth update:**

1. Run `alembic upgrade head` against the production database. This creates the new `hint_events` table. Without it the hint endpoints fail with a 500.
2. If production was created earlier with `create_tables()`, run `alembic stamp 0001_auth_foundation` once before upgrading.
3. Seed problems once if the table is empty: `python -m scripts.seed_problems`.
4. Existing users keep working only if their accounts live in the same database. Old tokens signed with a different `JWT_SECRET` are rejected, so users must log in again.
5. Redeploy the frontend, since `api.js` no longer sends `X-User-Id` and calls the new hint/coach endpoints.

Free hosting tiers can sleep when idle, so the first request after a pause may be slow or fail. The frontend shows "Could not reach the server" in that case; retry after a few seconds.

## Testing

```bash
cd backend
pytest -v
```

Tests use in-memory SQLite and a fake LLM. They cover scoring and prediction, problem topic mapping, seeding, list filters, submit/mark-solved rules, the admin endpoint, JWT access control (401 without a token, `X-User-Id` ignored), and the hint service.

## Limitations and future work

- **Synthetic vs real data gap:** the weak-topic model scores F1-macro 0.944 on a mixed split but 0.333 on the 30 real users only. Next step: collect 200+ real users with the scraper and re-run the real-only holdout.
- **Difficulty classifier:** could use sentence embeddings instead of TF-IDF.
- Hint "no full solution" protection is a heuristic guard plus prompt rules, not a guarantee.

## Built by

Samiksha Rana - [@SamikshaRana28](https://github.com/SamikshaRana28)