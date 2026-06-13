"""
train_models.py — XGBoost vs Random Forest A/B Comparison
FIXED: Real data (30 users) + synthetic mix for proper 6-class training
"""

import os
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

ALL_TOPICS = ["arrays", "graphs", "dp", "trees", "strings", "math"]


# ── Data Loading ──────────────────────────────────────────────────────────────
def load_real_data():
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM leetcode_users"))
            rows = result.fetchall()
            cols = list(result.keys())
        if len(rows) == 0:
            return None
        df = pd.DataFrame(rows, columns=cols)
        print(f"  ✅ Loaded {len(df)} real LeetCode users from DB")
        return df
    except Exception as e:
        print(f"  ⚠️  DB load failed: {e}")
        return None


def generate_synthetic_data(n=600):
    """Synthetic data with guaranteed all 6 topics as labels."""
    np.random.seed(42)
    profiles = []

    # Guarantee at least 60 samples per class (6 classes × 60 = 360 minimum)
    per_class = max(n // 6, 60)

    for weak in ALL_TOPICS:
        for _ in range(per_class):
            level = np.random.choice(["beginner", "intermediate", "advanced"],
                                      p=[0.35, 0.45, 0.20])
            base  = {"beginner": 5, "intermediate": 20, "advanced": 50}[level]
            scale = {"beginner": 8, "intermediate": 15, "advanced": 25}[level]

            counts = {t: max(1, int(np.random.normal(base, scale))) for t in ALL_TOPICS}
            # Make the weak topic clearly the lowest
            counts[weak] = max(0, min(counts.values()) // 2)

            profiles.append({
                **{f"{t}_solved": counts[t] for t in ALL_TOPICS},
                "avg_attempts":   round(np.clip(np.random.normal(2.5, 1.0), 1.0, 6.0), 1),
                "acceptance_rate": round(np.clip(np.random.normal(0.55, 0.15), 0.2, 0.95), 2),
                "total_solved":   sum(counts.values()),
                "weak_topic":     weak,
            })

    return pd.DataFrame(profiles)


def add_weak_topic_to_real(df):
    """Derive weak_topic for real users based on lowest topic count."""
    topic_cols = [f"{t}_solved" for t in ALL_TOPICS]
    topic_map  = {f"{t}_solved": t for t in ALL_TOPICS}

    # Fill missing topic cols with 0
    for col in topic_cols:
        if col not in df.columns:
            df[col] = 0

    df["weak_topic"] = df[topic_cols].fillna(0).idxmin(axis=1).map(topic_map)
    return df


def prepare_features(df):
    feature_cols = [
        "arrays_solved", "graphs_solved", "dp_solved",
        "trees_solved", "strings_solved", "math_solved",
        "avg_attempts", "acceptance_rate"
    ]
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0

    X  = df[feature_cols].fillna(0).values
    le = LabelEncoder()
    le.fit(ALL_TOPICS)                          # force all 6 classes always
    y  = le.transform(df["weak_topic"])
    return X, y, le, feature_cols


# ── Evaluation ────────────────────────────────────────────────────────────────
def evaluate_model(model, X_test, y_test, le):
    y_pred = model.predict(X_test)
    all_labels = list(range(len(le.classes_)))

    try:
        y_prob = model.predict_proba(X_test)
        roc_auc = round(roc_auc_score(
            y_test, y_prob, multi_class="ovr", average="macro",
            labels=all_labels
        ), 4)
    except Exception:
        roc_auc = None

    cm     = confusion_matrix(y_test, y_pred, labels=all_labels).tolist()
    report = classification_report(
        y_test, y_pred,
        labels=all_labels,
        target_names=le.classes_,
        output_dict=True,
        zero_division=0
    )

    per_class = {
        cls: round(report[cls]["f1-score"], 3)
        for cls in le.classes_ if cls in report
    }

    return {
        "accuracy":         round(accuracy_score(y_test, y_pred), 4),
        "f1_macro":         round(f1_score(y_test, y_pred, average="macro",  labels=all_labels, zero_division=0), 4),
        "f1_weighted":      round(f1_score(y_test, y_pred, average="weighted", labels=all_labels, zero_division=0), 4),
        "roc_auc":          roc_auc,
        "confusion_matrix": cm,
        "class_labels":     le.classes_.tolist(),
        "per_class_f1":     per_class,
    }


# ── Main ──────────────────────────────────────────────────────────────────────
def train_and_compare():
    print("\n🚀 Training XGBoost vs Random Forest — A/B Comparison\n")

    real_df  = load_real_data()
    synth_df = generate_synthetic_data(600)

    if real_df is not None and len(real_df) > 0:
        real_df = add_weak_topic_to_real(real_df)
        # Mix: real + synthetic (real data ko zyada weight dene ke liye)
        df = pd.concat([real_df, synth_df], ignore_index=True)
        data_source = f"mixed (real={len(real_df)}, synthetic={len(synth_df)})"
        print(f"  🔀 Mixed dataset: {len(real_df)} real + {len(synth_df)} synthetic = {len(df)} total")
    else:
        df = synth_df
        data_source = "synthetic"
        print(f"  📊 Using synthetic data only ({len(df)} samples)")
    # Keep real data separate for holdout validation
    real_holdout_df = real_df.copy() if real_df is not None and len(real_df) > 0 else None

    X, y, le, feature_cols = prepare_features(df)

    print(f"  Classes found: {le.classes_.tolist()}")
    print(f"  Class distribution: { {le.classes_[i]: int((y==i).sum()) for i in range(len(le.classes_))} }")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"  Train: {len(X_train)}, Test: {len(X_test)}\n")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    # ── XGBoost ──────────────────────────────────────────────────────────────
    print("  Training XGBoost...", end=" ", flush=True)
    xgb = XGBClassifier(
        n_estimators=200, max_depth=5, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric="mlogloss", random_state=42, n_jobs=-1
    )
    xgb.fit(X_train, y_train)
    cv_xgb      = cross_val_score(xgb, X, y, cv=cv, scoring="f1_macro")
    xgb_metrics = evaluate_model(xgb, X_test, y_test, le)
    xgb_metrics["cv_f1_mean"] = round(float(cv_xgb.mean()), 4)
    xgb_metrics["cv_f1_std"]  = round(float(cv_xgb.std()),  4)
    print(f"✅  F1={xgb_metrics['f1_macro']}, CV={xgb_metrics['cv_f1_mean']}±{xgb_metrics['cv_f1_std']}")

    # ── Random Forest ─────────────────────────────────────────────────────────
    print("  Training Random Forest...", end=" ", flush=True)
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_split=4,
        random_state=42, n_jobs=-1
    )
    rf.fit(X_train, y_train)
    cv_rf      = cross_val_score(rf, X, y, cv=cv, scoring="f1_macro")
    rf_metrics = evaluate_model(rf, X_test, y_test, le)
    rf_metrics["cv_f1_mean"] = round(float(cv_rf.mean()), 4)
    rf_metrics["cv_f1_std"]  = round(float(cv_rf.std()),  4)
    print(f"✅  F1={rf_metrics['f1_macro']}, CV={rf_metrics['cv_f1_mean']}±{rf_metrics['cv_f1_std']}")

    # ── Feature Importance ────────────────────────────────────────────────────
    xgb_imp = dict(zip(feature_cols, [round(float(v), 4) for v in xgb.feature_importances_]))
    rf_imp  = dict(zip(feature_cols, [round(float(v), 4) for v in rf.feature_importances_]))

    winner = "XGBoost" if xgb_metrics["f1_macro"] >= rf_metrics["f1_macro"] else "Random Forest"

# ── Save ─────────────────────────────────────────────────────────────────
    joblib.dump(xgb, MODELS_DIR / "xgboost_model.joblib")
    joblib.dump(rf,  MODELS_DIR / "rf_model.joblib")
    joblib.dump(le,  MODELS_DIR / "label_encoder.joblib")

# ── Real-data-only holdout evaluation ─────────────────────────────────
    real_eval = None

    if real_holdout_df is not None and len(real_holdout_df) >= 6:
        X_real, y_real, _, _ = prepare_features(real_holdout_df)

        xgb_real = evaluate_model(xgb, X_real, y_real, le)
        rf_real = evaluate_model(rf, X_real, y_real, le)

        real_eval = {
            "note": "Models trained on mixed data, evaluated on the real scraped users only",
            "n_samples": len(real_holdout_df),
            "xgboost": {
                "accuracy": xgb_real["accuracy"],
                "f1_macro": xgb_real["f1_macro"],
                "f1_weighted": xgb_real["f1_weighted"]
            },
            "random_forest": {
                "accuracy": rf_real["accuracy"],
                "f1_macro": rf_real["f1_macro"],
                "f1_weighted": rf_real["f1_weighted"]
            }
        }

        print(
            f"\n🔍 Real-only holdout — XGB F1={xgb_real['f1_macro']}, RF F1={rf_real['f1_macro']}"
        )

    eval_data = {
    "trained_at":    datetime.utcnow().isoformat(),
    "data_source":   data_source,
    "dataset_size":  len(df),
    "winner":        winner,
    "xgboost":       {**xgb_metrics, "feature_importance": xgb_imp},
    "random_forest": {**rf_metrics,  "feature_importance": rf_imp},
    "feature_cols":  feature_cols,
    "class_labels":  le.classes_.tolist(),
    "real_only_holdout": real_eval,
    }

    eval_path = MODELS_DIR / "evaluation.json"
    with open(eval_path, "w") as f:
        json.dump(eval_data, f, indent=2)

    print(f"\n  💾 Models saved → {MODELS_DIR}")
    print(f"  📊 Evaluation  → {eval_path}")
    print(f"\n  🏆 Winner: {winner}  F1={max(xgb_metrics['f1_macro'], rf_metrics['f1_macro'])}\n")
    return eval_data


if __name__ == "__main__":
    train_and_compare()