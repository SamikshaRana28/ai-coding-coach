"""
train_models.py — XGBoost vs Random Forest A/B Comparison
Trains on real scraped LeetCode data + synthetic fallback.
Saves both models + evaluation metrics to JSON for the frontend.

Usage: python ml/train_models.py
"""

import os
import sys
import json
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from sqlalchemy import create_engine, text
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold, train_test_split
from sklearn.metrics import (
    f1_score, roc_auc_score, confusion_matrix,
    classification_report, accuracy_score
)
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

load_dotenv()
BASE = Path(__file__).parent
MODELS_DIR = BASE / "models"
MODELS_DIR.mkdir(exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost/coding_coach")


# ── Data Loading ─────────────────────────────────────────────────────────────
def load_real_data() -> pd.DataFrame | None:
    """Try loading real scraped LeetCode users from DB."""
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM leetcode_users"))
            rows = result.fetchall()
            cols = result.keys()
        if len(rows) < 10:
            return None
        df = pd.DataFrame(rows, columns=cols)
        print(f"  ✅ Loaded {len(df)} real LeetCode users from DB")
        return df
    except Exception as e:
        print(f"  ⚠️  DB load failed: {e}")
        return None


def generate_synthetic_data(n: int = 600) -> pd.DataFrame:
    """Fallback synthetic dataset with realistic distributions."""
    np.random.seed(42)
    profiles = []

    topics = ["arrays", "graphs", "dp", "trees", "strings", "math"]
    weak_topics = topics  # label = weakest topic

    for _ in range(n):
        # Random skill level
        level = np.random.choice(["beginner", "intermediate", "advanced"],
                                  p=[0.35, 0.45, 0.20])

        base = {"beginner": 5, "intermediate": 20, "advanced": 50}[level]
        scale = {"beginner": 8, "intermediate": 15, "advanced": 25}[level]

        counts = {t: max(0, int(np.random.normal(base, scale))) for t in topics}

        # Inject a clear weak topic (for realistic label)
        weak = np.random.choice(topics)
        counts[weak] = max(0, counts[weak] // 3)

        total = sum(counts.values())
        acceptance = round(np.clip(np.random.normal(0.55, 0.15), 0.2, 0.95), 2)
        avg_attempts = round(np.clip(np.random.normal(2.5, 1.0), 1.0, 6.0), 1)

        profiles.append({
            **counts,
            "avg_attempts": avg_attempts,
            "acceptance_rate": acceptance,
            "total_solved": total,
            "weak_topic": weak,
        })

    return pd.DataFrame(profiles)


def prepare_features(df: pd.DataFrame):
    """Extract feature matrix X and label vector y."""
    feature_cols = [
        "arrays_solved", "graphs_solved", "dp_solved",
        "trees_solved", "strings_solved", "math_solved",
        "avg_attempts", "acceptance_rate"
    ]

    # If real data (no weak_topic column), derive it
    if "weak_topic" not in df.columns:
        topic_cols = ["arrays_solved", "graphs_solved", "dp_solved",
                      "trees_solved", "strings_solved", "math_solved"]
        topic_map = {
            "arrays_solved": "arrays",  "graphs_solved": "graphs",
            "dp_solved": "dp",          "trees_solved": "trees",
            "strings_solved": "strings","math_solved": "math"
        }
        df["weak_topic"] = df[topic_cols].idxmin(axis=1).map(topic_map)

    # Fill missing feature cols with 0
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0

    X = df[feature_cols].fillna(0).values
    le = LabelEncoder()
    y = le.fit_transform(df["weak_topic"])
    return X, y, le, feature_cols


# ── Training ─────────────────────────────────────────────────────────────────
def evaluate_model(model, X_test, y_test, le) -> dict:
    """Full evaluation metrics for one model."""
    y_pred = model.predict(X_test)

    # ROC-AUC (multiclass OvR)
    try:
        y_prob = model.predict_proba(X_test)
        roc_auc = round(roc_auc_score(y_test, y_prob, multi_class="ovr", average="macro"), 4)
    except Exception:
        roc_auc = None

    cm = confusion_matrix(y_test, y_pred).tolist()
    report = classification_report(y_test, y_pred,
                                   target_names=le.classes_, output_dict=True)

    # Per-class F1
    per_class = {
        cls: round(report[cls]["f1-score"], 3)
        for cls in le.classes_ if cls in report
    }

    return {
        "accuracy":        round(accuracy_score(y_test, y_pred), 4),
        "f1_macro":        round(f1_score(y_test, y_pred, average="macro"), 4),
        "f1_weighted":     round(f1_score(y_test, y_pred, average="weighted"), 4),
        "roc_auc":         roc_auc,
        "confusion_matrix": cm,
        "class_labels":    le.classes_.tolist(),
        "per_class_f1":    per_class,
    }


def train_and_compare():
    print("\n🚀 Training XGBoost vs Random Forest — A/B Comparison\n")

    # Load data
    df = load_real_data()
    data_source = "real"
    if df is None or len(df) < 30:
        print("  📊 Using synthetic data (run scrape_leetcode.py for real data)")
        df = generate_synthetic_data(700)
        data_source = "synthetic"

    X, y, le, feature_cols = prepare_features(df)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"  Dataset: {len(df)} samples ({data_source}), {len(le.classes_)} classes")
    print(f"  Train: {len(X_train)}, Test: {len(X_test)}\n")

    # ── XGBoost ──────────────────────────────────────────────────────────────
    print("  Training XGBoost...", end=" ", flush=True)
    xgb = XGBClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8,
        use_label_encoder=False, eval_metric="mlogloss",
        random_state=42, n_jobs=-1
    )
    xgb.fit(X_train, y_train)
    cv_xgb = cross_val_score(xgb, X, y, cv=StratifiedKFold(5), scoring="f1_macro")
    xgb_metrics = evaluate_model(xgb, X_test, y_test, le)
    xgb_metrics["cv_f1_mean"] = round(cv_xgb.mean(), 4)
    xgb_metrics["cv_f1_std"]  = round(cv_xgb.std(), 4)
    print(f"✅  F1={xgb_metrics['f1_macro']}, CV={xgb_metrics['cv_f1_mean']}±{xgb_metrics['cv_f1_std']}")

    # ── Random Forest ─────────────────────────────────────────────────────────
    print("  Training Random Forest...", end=" ", flush=True)
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_split=4,
        random_state=42, n_jobs=-1
    )
    rf.fit(X_train, y_train)
    cv_rf = cross_val_score(rf, X, y, cv=StratifiedKFold(5), scoring="f1_macro")
    rf_metrics = evaluate_model(rf, X_test, y_test, le)
    rf_metrics["cv_f1_mean"] = round(cv_rf.mean(), 4)
    rf_metrics["cv_f1_std"]  = round(cv_rf.std(), 4)
    print(f"✅  F1={rf_metrics['f1_macro']}, CV={rf_metrics['cv_f1_mean']}±{rf_metrics['cv_f1_std']}")

    # ── Feature Importance ────────────────────────────────────────────────────
    xgb_importance = dict(zip(feature_cols, [round(float(v), 4) for v in xgb.feature_importances_]))
    rf_importance  = dict(zip(feature_cols, [round(float(v), 4) for v in rf.feature_importances_]))

    # ── Winner ────────────────────────────────────────────────────────────────
    winner = "XGBoost" if xgb_metrics["f1_macro"] >= rf_metrics["f1_macro"] else "Random Forest"

    # ── Save models ───────────────────────────────────────────────────────────
    joblib.dump(xgb, MODELS_DIR / "xgboost_model.joblib")
    joblib.dump(rf,  MODELS_DIR / "rf_model.joblib")
    joblib.dump(le,  MODELS_DIR / "label_encoder.joblib")
    print(f"\n  💾 Models saved to {MODELS_DIR}")

    # ── Save evaluation JSON for frontend ─────────────────────────────────────
    eval_data = {
        "trained_at":   datetime.utcnow().isoformat(),
        "data_source":  data_source,
        "dataset_size": len(df),
        "winner":       winner,
        "xgboost":      {**xgb_metrics, "feature_importance": xgb_importance},
        "random_forest": {**rf_metrics, "feature_importance": rf_importance},
        "feature_cols": feature_cols,
        "class_labels": le.classes_.tolist(),
    }

    eval_path = MODELS_DIR / "evaluation.json"
    with open(eval_path, "w") as f:
        json.dump(eval_data, f, indent=2)

    print(f"  📊 Evaluation saved to {eval_path}")
    print(f"\n  🏆 Winner: {winner} (F1={max(xgb_metrics['f1_macro'], rf_metrics['f1_macro'])})\n")
    return eval_data


if __name__ == "__main__":
    train_and_compare()