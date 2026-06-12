import pandas as pd
import numpy as np
import random

random.seed(42)
np.random.seed(42)

topics = ["arrays", "graphs", "dp", "trees", "strings", "math"]

def generate_user(i):
    weak = random.choice(topics)
    data = {
        "user_id": i,
        "arrays_solved":  random.randint(0, 50),
        "graphs_solved":  random.randint(0, 30),
        "dp_solved":      random.randint(0, 40),
        "trees_solved":   random.randint(0, 35),
        "strings_solved": random.randint(0, 45),
        "math_solved":    random.randint(0, 25),
        "avg_attempts":   round(random.uniform(1.0, 5.0), 2),
        "acceptance_rate": round(random.uniform(0.2, 0.95), 2),
        "weak_topic": weak
    }
    # Make the weak topic have fewer solves (realistic!)
    data[weak + "_solved"] = random.randint(0, 5)
    return data

rows = [generate_user(i) for i in range(1, 1001)]
df = pd.DataFrame(rows)
df.to_csv("user_data.csv", index=False)
print(f"Dataset created! Shape: {df.shape}")
print(df.head())
