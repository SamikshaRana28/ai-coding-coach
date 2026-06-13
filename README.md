

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

##  Testing

```bash
cd backend
pytest -v
```
3 tests covering readiness score calculation and weak-topic prediction.

##  Limitations & Future Work

- **Synthetic vs real data gap:** The weak-topic model achieves F1-macro=0.944 on a mixed train/test split (630 samples: 30 real + 600 synthetic), but only F1-macro=0.333 (XGBoost) when evaluated exclusively on the 30 real users. This indicates the model currently learns synthetic data patterns well but does not yet generalize strongly to real-world data. **Root cause:** 30 real samples is too small a holdout to be statistically reliable, and synthetic data was generated with artificially clean class separability. **Next step:** scale real data collection to 200+ users via the scraper, and re-run the real-only holdout at that scale.
- **Difficulty classifier:** TF-IDF + Logistic Regression (with `related_topics` and class balancing) achieves F1-weighted=0.487, F1-macro=0.47. Future improvement: replace TF-IDF with sentence embeddings (reusing the existing `all-MiniLM-L6-v2` model from the recommender) for richer semantic features.
- **Single-user demo data** for progress tracking — multi-user authentication not implemented.


> Deployment in progress — run locally via Docker or Quick Start below.  



##  Built By

Samiksha Rana — [@SamikshaRana28](https://github.com/SamikshaRana28)