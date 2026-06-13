<!-- # 🤖 AI Coding Interview Coach

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

Samiksha Rana — [@SamikshaRana28](https://github.com/SamikshaRana28) -->

























<!-- # 🤖 AI Coding Interview Coach

An intelligent coding interview preparation platform powered by ML + NLP + AI.

## 🚀 Live Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/analyze` | POST | AI code review — time/space complexity, bugs, approach |
| `/predict` | POST | Predicts your weakest DSA topic using ML |
| `/predict-difficulty` | POST | Predicts question difficulty (Easy/Medium/Hard) using NLP |
| `/recommend` | POST | Top 3 similar LeetCode questions using NLP |
| `/score` | POST | Interview Readiness Score (0–100) |
| `/model-evaluation` | GET | XGBoost vs Random Forest comparison metrics |
| `/progress/{user_id}` | GET | Weekly readiness score progression |
| `/dataset-stats` | GET | Real LeetCode user data stats |
| `/attempts/{user_id}` | GET | User attempt history |

## 🧠 ML Models Used

### 1. Weak Topic Predictor — A/B Comparison
- **Models:** Random Forest vs XGBoost, compared with 5-fold cross-validation
- **Data:** 30 real scraped LeetCode profiles + 600 synthetic samples (630 total)
- **Features:** arrays_solved, graphs_solved, dp_solved, trees_solved, strings_solved, math_solved, avg_attempts, acceptance_rate
- **Results:**
  - **XGBoost (winner):** F1-macro 0.9437, ROC-AUC 0.9988, CV F1 0.954 ± 0.016
  - **Random Forest:** F1-macro 0.9327, ROC-AUC 0.9977, CV F1 0.920 ± 0.019
- **Labels:** arrays, dp, graphs, math, strings, trees

### 2. Difficulty Classifier (NLP)
- **Model:** TF-IDF + Logistic Regression
- **Input:** Question title + description
- **Output:** Easy / Medium / Hard with confidence scores
- **Dataset:** LeetCode 500-question dataset

### 3. Similar Questions Recommender (NLP)
- **Model:** Sentence Transformers (`all-MiniLM-L6-v2`)
- **Technique:** Cosine similarity on question embeddings
- **Dataset:** LeetCode 500 questions
- **Output:** Top 3 semantically similar problems

### 4. Interview Readiness Score
- **Type:** Weighted formula
- **Components:** Volume (30pts) + Variety (25pts) + Acceptance Rate (25pts) + Efficiency (20pts)
- **Output:** Score 0–100 + level (Just Starting → Interview Ready 🔥)

## 🛠️ Tech Stack

**Backend:** FastAPI, Python, PostgreSQL, SQLAlchemy
**ML:** Scikit-learn, XGBoost, Sentence Transformers
**AI:** Groq API (LLaMA 3.3 70B)
**Frontend:** React
**Infra:** Docker, GitHub Codespaces

## 📁 Project Structure
ai-coding-coach/

├── backend/

│   ├── main.py              # FastAPI app + all endpoints

│   ├── models.py            # PostgreSQL schema

│   ├── scrape_leetcode.py   # Scrapes real LeetCode user data

│   └── ml/

│       ├── train_models.py        # XGBoost vs RF A/B training

│       ├── difficulty_classifier.py # Difficulty NLP classifier

│       ├── predict.py             # Weak topic predictor

│       ├── recommender.py         # NLP similarity engine

│       ├── score.py               # Readiness score calculator

│       ├── progress.py            # Progress tracking

│       └── models/                # Saved model artifacts + evaluation.json

├── data/

│   ├── user_data.csv             # Synthetic training data

│   └── leetcode_dataset - lc.csv # LeetCode problems dataset

└── frontend/

└── src/                  # React UI
## ⚡ Quick Start

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --port 8000 --reload

# Train ML models (run once)
python ml/train_models.py

# Scrape real LeetCode data (optional, run once)
python scrape_leetcode.py
```

## 📊 Model Evaluation (XGBoost vs Random Forest)

| Model | Accuracy | F1-Macro | ROC-AUC | CV F1 |
|-------|----------|----------|---------|-------|
| **XGBoost** 🏆 | 0.944 | 0.944 | 0.999 | 0.954 ± 0.016 |
| Random Forest | 0.937 | 0.933 | 0.998 | 0.920 ± 0.019 |

Trained on 630 samples (30 real LeetCode users + 600 synthetic).

## 👩‍💻 Built By

Samiksha Rana — [@SamikshaRana28](https://github.com/SamikshaRana28) -->












# 🤖 AI Coding Interview Coach

An intelligent coding interview preparation platform that combines AI-powered code review, ML-based weak-topic prediction, and NLP-driven question recommendations.

## 🎯 What It Does

Given your LeetCode solving history, this platform:
- Predicts which DSA topic you're weakest in (ML classification)
- Recommends similar practice questions (NLP/semantic search)
- Reviews your code for time/space complexity, bugs, and better approaches (LLM)
- Predicts difficulty of any question (NLP classification)
- Calculates an "Interview Readiness Score" (0-100)
- Tracks your progress over time

## 🚀 Live Demo

[Add your Render link here]

## 🛠️ Tech Stack

**Backend:** FastAPI, Python, PostgreSQL, SQLAlchemy
**ML:** Scikit-learn, XGBoost, Sentence Transformers
**AI:** Groq API (LLaMA 3.3 70B)
**Frontend:** React, Vite, Tailwind CSS, Recharts, Monaco Editor
**Infra:** Docker, GitHub Codespaces, Render

## 📡 API Endpoints

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

## 🧠 ML Models

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

## 📁 Project Structure
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
## ⚡ Quick Start

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
docker-compose up --build
```

## ✅ Testing

```bash
cd backend
pytest -v
```
3 tests covering readiness score calculation and weak-topic prediction.

## ⚠️ Limitations & Future Work

- **Synthetic vs real data gap:** The weak-topic model achieves F1-macro=0.944 on a mixed train/test split (630 samples: 30 real + 600 synthetic), but only F1-macro=0.333 (XGBoost) when evaluated exclusively on the 30 real users. This indicates the model currently learns synthetic data patterns well but does not yet generalize strongly to real-world data. **Root cause:** 30 real samples is too small a holdout to be statistically reliable, and synthetic data was generated with artificially clean class separability. **Next step:** scale real data collection to 200+ users via the scraper, and re-run the real-only holdout at that scale.
- **Difficulty classifier:** TF-IDF + Logistic Regression (with `related_topics` and class balancing) achieves F1-weighted=0.487, F1-macro=0.47. Future improvement: replace TF-IDF with sentence embeddings (reusing the existing `all-MiniLM-L6-v2` model from the recommender) for richer semantic features.
- **Single-user demo data** for progress tracking — multi-user authentication not implemented.

## 👩‍💻 Built By

Samiksha Rana — [@SamikshaRana28](https://github.com/SamikshaRana28)