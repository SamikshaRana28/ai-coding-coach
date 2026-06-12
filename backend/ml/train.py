import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report
from xgboost import XGBClassifier
import joblib
import os

# Data ka path (data folder se)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "user_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "ml", "model.pkl")
ENCODER_PATH = os.path.join(BASE_DIR, "ml", "label_encoder.pkl")

# Data load karo
df = pd.read_csv(DATA_PATH)
print(f"Data loaded: {df.shape}")

# Features aur label
features = ["arrays_solved", "graphs_solved", "dp_solved",
            "trees_solved", "strings_solved", "math_solved",
            "avg_attempts", "acceptance_rate"]
X = df[features]
y = df["weak_topic"]

# Labels → numbers
le = LabelEncoder()
y_encoded = le.fit_transform(y)

# Train/Test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y_encoded, test_size=0.2, random_state=42
)

# Model 1: Random Forest
rf = RandomForestClassifier(n_estimators=100, random_state=42)
rf.fit(X_train, y_train)
rf_score = cross_val_score(rf, X, y_encoded, cv=5, scoring="f1_weighted").mean()
print(f"Random Forest F1: {rf_score:.3f}")

# Model 2: XGBoost
xgb = XGBClassifier(n_estimators=100, random_state=42,
                    eval_metric="mlogloss", verbosity=0)
xgb.fit(X_train, y_train)
xgb_score = cross_val_score(xgb, X, y_encoded, cv=5, scoring="f1_weighted").mean()
print(f"XGBoost F1:       {xgb_score:.3f}")

# Better model save karo
best = xgb if xgb_score > rf_score else rf
joblib.dump(best, MODEL_PATH)
joblib.dump(le, ENCODER_PATH)
print(f"\nSaved: model.pkl + label_encoder.pkl in backend/ml/")
print("\nClassification Report:")
print(classification_report(y_test, best.predict(X_test),
      target_names=le.classes_))