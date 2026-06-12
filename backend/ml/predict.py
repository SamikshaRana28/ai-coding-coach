import joblib
import os
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")
ENCODER_PATH = os.path.join(BASE_DIR, "label_encoder.pkl")

# Model ek baar load karo (server start pe)
model = joblib.load(MODEL_PATH)
label_encoder = joblib.load(ENCODER_PATH)

def predict_weak_topic(
    arrays_solved: int,
    graphs_solved: int,
    dp_solved: int,
    trees_solved: int,
    strings_solved: int,
    math_solved: int,
    avg_attempts: float,
    acceptance_rate: float
) -> dict:
    features = np.array([[
        arrays_solved, graphs_solved, dp_solved,
        trees_solved, strings_solved, math_solved,
        avg_attempts, acceptance_rate
    ]])
    prediction = model.predict(features)[0]
    topic = label_encoder.inverse_transform([prediction])[0]
    
    # Probabilities bhi nikalo
    probs = model.predict_proba(features)[0]
    all_topics = label_encoder.inverse_transform(range(len(probs)))
    topic_probs = {t: round(float(p), 3) for t, p in zip(all_topics, probs)}
    
    return {
        "weak_topic": topic,
        "confidence": round(float(max(probs)), 3),
        "all_probabilities": topic_probs
    }