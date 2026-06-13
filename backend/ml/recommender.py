# import pandas as pd
# import numpy as np
# from sentence_transformers import SentenceTransformer
# from sklearn.metrics.pairwise import cosine_similarity
# import os

# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# DATA_PATH = os.path.join(BASE_DIR, "..", "data", "leetcode_dataset - lc.csv")

# # Model load karo (pehli baar ~1 min lagega download mein)
# print("Loading sentence transformer model...")
# model = SentenceTransformer("all-MiniLM-L6-v2")

# # Dataset load karo
# print("Loading LeetCode dataset...")
# df = pd.read_csv(DATA_PATH)

# # Sirf kaam ke columns rakho, NaN hatao
# df = df[["id", "title", "description", "difficulty", "related_topics"]].dropna()
# df = df.head(500)  # pehle 500 questions use karo (fast rahega)

# # Embeddings banao (title + description combine karke)
# print("Generating embeddings... (1-2 min lagega pehli baar)")
# texts = (df["title"] + " " + df["description"].str[:300]).tolist()
# embeddings = model.encode(texts, show_progress_bar=True)

# print(f"Ready! {len(df)} questions loaded.")

# def get_similar_questions(question_title: str, top_n: int = 3) -> list:
#     # Input question ka embedding banao
#     query_embedding = model.encode([question_title])
    
#     # Cosine similarity calculate karo
#     similarities = cosine_similarity(query_embedding, embeddings)[0]
    
#     # Top N similar questions nikalo (khud ko exclude karo)
#     top_indices = similarities.argsort()[::-1]
    
#     results = []
#     for idx in top_indices:
#         title = df.iloc[idx]["title"]
#         if title.lower() == question_title.lower():
#             continue  # same question skip
#         results.append({
#             "title": title,
#             "difficulty": df.iloc[idx]["difficulty"],
#             "topics": df.iloc[idx]["related_topics"],
#             "similarity_score": round(float(similarities[idx]), 3)
#         })
#         if len(results) == top_n:
#             break
    
#     return results









import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

print("Loading precomputed embeddings...")
embeddings = np.load(os.path.join(BASE_DIR, "embeddings.npz"))["embeddings"]
df = pd.read_pickle(os.path.join(BASE_DIR, "questions_df.pkl"))

print("Loading sentence transformer model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

print(f"Ready! {len(df)} questions loaded.")

def get_similar_questions(question_title: str, top_n: int = 3) -> list:
    query_embedding = model.encode([question_title])
    similarities = cosine_similarity(query_embedding, embeddings)[0]
    top_indices = similarities.argsort()[::-1]

    results = []
    for idx in top_indices:
        title = df.iloc[idx]["title"]
        if title.lower() == question_title.lower():
            continue
        results.append({
            "title": title,
            "difficulty": df.iloc[idx]["difficulty"],
            "topics": df.iloc[idx]["related_topics"],
            "similarity_score": round(float(similarities[idx]), 3)
        })
        if len(results) == top_n:
            break

    return results