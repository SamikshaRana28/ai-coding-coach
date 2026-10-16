"""
difficulty_predict.py - the difficulty classifier as a plain function.

POST /predict-difficulty and the Coach tool both call predict_difficulty().
Models load on first use.
"""
from pathlib import Path

import joblib

MODELS_DIR = Path(__file__).parent / "models"
_MODEL_PATH = MODELS_DIR / "difficulty_model.joblib"
_VEC_PATH = MODELS_DIR / "difficulty_vectorizer.joblib"

_model = None
_vectorizer = None


class ModelNotTrained(RuntimeError):
    pass


def _load():
    global _model, _vectorizer
    if _model is None or _vectorizer is None:
        if not (_MODEL_PATH.exists() and _VEC_PATH.exists()):
            raise ModelNotTrained("Difficulty model not trained yet")
        _model = joblib.load(_MODEL_PATH)
        _vectorizer = joblib.load(_VEC_PATH)
    return _model, _vectorizer


def predict_difficulty(title: str, description: str = "") -> dict:
    model, vectorizer = _load()
    text = title + " " + description[:300]
    vec = vectorizer.transform([text])
    pred = model.predict(vec)[0]
    probs = model.predict_proba(vec)[0]
    return {
        "predicted_difficulty": pred,
        "confidence": round(float(max(probs)), 3),
        "all_probabilities": {c: round(float(p), 3) for c, p in zip(model.classes_, probs)},
    }
