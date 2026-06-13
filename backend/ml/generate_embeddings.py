import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "leetcode_dataset - lc.csv")
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "embeddings.npz")

print("Loading model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

print("Loading dataset...")
df = pd.read_csv(DATA_PATH)
df = df[["id", "title", "description", "difficulty", "related_topics"]].dropna()
df = df.head(500)

print("Generating embeddings...")
texts = (df["title"] + " " + df["description"].str[:300]).tolist()
embeddings = model.encode(texts, show_progress_bar=True)

np.savez(OUT_PATH, embeddings=embeddings)
df.to_pickle(os.path.join(os.path.dirname(os.path.abspath(__file__)), "questions_df.pkl"))

print(f"Saved {len(df)} embeddings to {OUT_PATH}")