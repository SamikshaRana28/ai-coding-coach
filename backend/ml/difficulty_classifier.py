# import os
# import joblib
# import pandas as pd
# from sklearn.feature_extraction.text import TfidfVectorizer
# from sklearn.linear_model import LogisticRegression
# from sklearn.model_selection import train_test_split
# from sklearn.metrics import accuracy_score, f1_score, classification_report

# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DATA_PATH = os.path.join(BASE_DIR, "..", "data", "leetcode_dataset - lc.csv")
# MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
# os.makedirs(MODELS_DIR, exist_ok=True)

# print("Loading dataset...")
# df = pd.read_csv(DATA_PATH)
# df = df[["title", "description", "difficulty"]].dropna()

# X = df["title"] + " " + df["description"].str[:300]
# y = df["difficulty"]

# X_train, X_test, y_train, y_test = train_test_split(
#     X, y, test_size=0.2, random_state=42, stratify=y
# )

# vectorizer = TfidfVectorizer(max_features=3000, stop_words="english")
# X_train_vec = vectorizer.fit_transform(X_train)
# X_test_vec = vectorizer.transform(X_test)

# clf = LogisticRegression(max_iter=1000)
# clf.fit(X_train_vec, y_train)

# preds = clf.predict(X_test_vec)
# print("Accuracy:", accuracy_score(y_test, preds))
# print("F1 (weighted):", f1_score(y_test, preds, average="weighted"))
# print(classification_report(y_test, preds))

# joblib.dump(clf, os.path.join(MODELS_DIR, "difficulty_model.joblib"))
# joblib.dump(vectorizer, os.path.join(MODELS_DIR, "difficulty_vectorizer.joblib"))
# print("Saved difficulty_model.joblib + difficulty_vectorizer.joblib")











import os
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, classification_report

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "leetcode_dataset - lc.csv")
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
os.makedirs(MODELS_DIR, exist_ok=True)

print("Loading dataset...")
df = pd.read_csv(DATA_PATH)
df = df[["title", "description", "difficulty"]].dropna()

X = (
    df["title"]
    + " "
    + df["description"].str[:300]
    + " "
    + df["related_topics"].fillna("")
)
y = df["difficulty"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

vectorizer = TfidfVectorizer(max_features=3000, stop_words="english")
X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)

clf = LogisticRegression(
    max_iter=1000,
    class_weight="balanced"
)
clf.fit(X_train_vec, y_train)

preds = clf.predict(X_test_vec)
print("Accuracy:", accuracy_score(y_test, preds))
print("F1 (weighted):", f1_score(y_test, preds, average="weighted"))
print(classification_report(y_test, preds))

joblib.dump(clf, os.path.join(MODELS_DIR, "difficulty_model.joblib"))
joblib.dump(vectorizer, os.path.join(MODELS_DIR, "difficulty_vectorizer.joblib"))
print("Saved difficulty_model.joblib + difficulty_vectorizer.joblib")