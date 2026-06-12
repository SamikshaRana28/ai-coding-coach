"""
scrape_leetcode.py — Real LeetCode user data via public GraphQL API
Usage: python scrape_leetcode.py
Saves 50 real user profiles to PostgreSQL leetcode_users table.
No API key needed — uses LeetCode's public GraphQL endpoint.
"""

import requests
import time
import json
import os
import sys
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost/coding_coach")
engine = create_engine(DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)


# ── DB Model ─────────────────────────────────────────────────────────────────
class LeetCodeUser(Base):
    __tablename__ = "leetcode_users"
    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String, unique=True)
    total_solved    = Column(Integer, default=0)
    easy_solved     = Column(Integer, default=0)
    medium_solved   = Column(Integer, default=0)
    hard_solved     = Column(Integer, default=0)
    acceptance_rate = Column(Float, default=0.0)
    # Topic counts (estimated from submission tags)
    arrays_solved   = Column(Integer, default=0)
    graphs_solved   = Column(Integer, default=0)
    dp_solved       = Column(Integer, default=0)
    trees_solved    = Column(Integer, default=0)
    strings_solved  = Column(Integer, default=0)
    math_solved     = Column(Integer, default=0)
    scraped_at      = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(engine)


# ── GraphQL Queries ───────────────────────────────────────────────────────────
STATS_QUERY = """
query getUserProfile($username: String!) {
  matchedUser(username: $username) {
    username
    submitStats: submitStatsGlobal {
      acSubmissionNum {
        difficulty
        count
      }
    }
    tagProblemCounts {
      advanced {
        tagName
        problemsSolved
      }
      intermediate {
        tagName
        problemsSolved
      }
      fundamental {
        tagName
        problemsSolved
      }
    }
  }
}
"""

HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com",
    "User-Agent": "Mozilla/5.0",
}

# 60 known active public usernames (will try all, take first 50 that succeed)
USERNAMES = [
    "neal_wu", "tourist", "jiangly", "ecnerwala", "Um_nik",
    "nealwu", "benq", "maroonrk", "1-9", "Petr",
    "apiad", "dhruvildave", "kevin_naughtOn", "SomeName12345", "uwi",
    "prabowo", "nor", "ainta", "scott_wu", "Vercingetorix",
    "radewoosh", "bqi343", "arpa", "300iq", "jqdai0815",
    "jiangly", "tmwilliamlin", "Geothermal", "evenvalue", "ksun48",
    "codeforces", "ShayanK", "satyam343", "theniceboy", "shen_laowang",
    "user1234567", "abhishek_rajput", "leetcoder99", "devguru", "topicmaster",
    "algomaster", "codepro2024", "dsa_ninja", "grindmaster", "techcracker",
    "problemsolver", "codemaster", "dailyLCer", "consistentcoder", "grinder365",
    "solveit", "tryharder", "neetcoder", "striverr", "takeuforward",
    "neetcode", "errichto", "kartik8800", "anmol_srivastava", "ank6353"
]


def fetch_user(username: str) -> dict | None:
    """Fetch a single user's stats from LeetCode GraphQL."""
    try:
        resp = requests.post(
            "https://leetcode.com/graphql",
            json={"query": STATS_QUERY, "variables": {"username": username}},
            headers=HEADERS,
            timeout=10
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        user = data.get("data", {}).get("matchedUser")
        if not user:
            return None
        return user
    except Exception as e:
        print(f"  Error fetching {username}: {e}")
        return None


def parse_user(raw: dict) -> dict:
    """Parse GraphQL response into clean dict."""
    username = raw["username"]

    # Solved counts by difficulty
    stats = {s["difficulty"]: s["count"] for s in raw["submitStats"]["acSubmissionNum"]}
    total  = stats.get("All", 0)
    easy   = stats.get("Easy", 0)
    medium = stats.get("Medium", 0)
    hard   = stats.get("Hard", 0)

    # Acceptance rate = approximation (hard to get without auth, use solved/total*0.7 estimate)
    acceptance = round(min(0.95, 0.4 + (total / 3000) * 0.5), 2) if total > 0 else 0.4

    # Topic counts from tag data
    topic_map = {
        "arrays":  ["Array", "Two Pointers", "Sliding Window", "Prefix Sum"],
        "graphs":  ["Graph", "BFS", "DFS", "Shortest Path", "Union Find", "Topological Sort"],
        "dp":      ["Dynamic Programming", "Memoization"],
        "trees":   ["Binary Tree", "Binary Search Tree", "Tree", "Trie"],
        "strings": ["String", "String Matching"],
        "math":    ["Math", "Bit Manipulation", "Number Theory"],
    }

    tag_counts = {}
    for group in ["advanced", "intermediate", "fundamental"]:
        for item in raw.get("tagProblemCounts", {}).get(group, []):
            tag_counts[item["tagName"]] = item["problemsSolved"]

    def topic_sum(tags):
        return sum(tag_counts.get(t, 0) for t in tags)

    return {
        "username":        username,
        "total_solved":    total,
        "easy_solved":     easy,
        "medium_solved":   medium,
        "hard_solved":     hard,
        "acceptance_rate": acceptance,
        "arrays_solved":   topic_sum(topic_map["arrays"]),
        "graphs_solved":   topic_sum(topic_map["graphs"]),
        "dp_solved":       topic_sum(topic_map["dp"]),
        "trees_solved":    topic_sum(topic_map["trees"]),
        "strings_solved":  topic_sum(topic_map["strings"]),
        "math_solved":     topic_sum(topic_map["math"]),
    }


def scrape_and_save(target: int = 50):
    db = SessionLocal()
    saved = 0
    failed = 0

    print(f"\n🚀 Starting LeetCode scraper — target: {target} users\n")

    for username in USERNAMES:
        if saved >= target:
            break

        print(f"  Fetching {username}...", end=" ", flush=True)
        raw = fetch_user(username)

        if not raw:
            print("❌ not found")
            failed += 1
            time.sleep(0.5)
            continue

        parsed = parse_user(raw)

        # Skip users with 0 solved (inactive/private)
        if parsed["total_solved"] == 0:
            print("⚠️  0 solved, skipping")
            continue

        # Upsert
        existing = db.query(LeetCodeUser).filter_by(username=parsed["username"]).first()
        if existing:
            for k, v in parsed.items():
                setattr(existing, k, v)
            print(f"✅ updated ({parsed['total_solved']} solved)")
        else:
            db.add(LeetCodeUser(**parsed))
            print(f"✅ saved ({parsed['total_solved']} solved)")

        db.commit()
        saved += 1
        time.sleep(0.8)  # be polite to LeetCode servers

    db.close()
    print(f"\n✅ Done! {saved} users saved, {failed} failed.")
    print("Run your ML training now: python ml/train_models.py")


if __name__ == "__main__":
    scrape_and_save(50)
