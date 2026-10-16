"""
Seed the `problems` table from data/leetcode_dataset - lc.csv.

Uses the SAME 500 questions the recommender (ml/generate_embeddings.py) uses:
rows that have id/title/description/difficulty/related_topics, first 500 in file order.

Idempotent: problems are keyed by `slug`. Running it again updates rows in place
(never duplicates) and never touches problems added by hand (source != "leetcode").

Usage (from backend/, after `alembic upgrade head`):
    python -m scripts.seed_problems
    python -m scripts.seed_problems --csv "/path/to/file.csv" --limit 500
"""
import argparse
import os
import sys
from pathlib import Path

import pandas as pd

# allow `python scripts/seed_problems.py` as well as `python -m scripts.seed_problems`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from problem_utils import (  # noqa: E402
    map_topics, normalize_difficulty, slug_from_url, slugify,
)

SOURCE = "leetcode"
DEFAULT_LIMIT = 500
# Mirrors ml/generate_embeddings.py: df[cols].dropna().head(500)
RECOMMENDER_COLS = ["id", "title", "description", "difficulty", "related_topics"]


def default_csv_path() -> Path:
    # backend/scripts/seed_problems.py -> <repo>/data/...   (in Docker: /app/../data = /data)
    return Path(__file__).resolve().parents[2] / "data" / "leetcode_dataset - lc.csv"


def load_leetcode_rows(csv_path=None, limit: int = DEFAULT_LIMIT) -> list:
    """Read the CSV and return ready-to-insert dicts (pure; no database needed)."""
    csv_path = Path(csv_path) if csv_path else default_csv_path()
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {csv_path}\n"
            "Pass --csv /path/to/'leetcode_dataset - lc.csv' (in Docker mount ./data to /data)."
        )

    df = pd.read_csv(csv_path)
    df = df.dropna(subset=RECOMMENDER_COLS).head(limit)

    rows, seen = [], set()
    for rec in df.to_dict("records"):
        difficulty = normalize_difficulty(rec["difficulty"])
        if difficulty is None:
            print(f"  skipping {rec['title']!r}: unknown difficulty {rec['difficulty']!r}")
            continue

        title = str(rec["title"]).strip()
        url = rec.get("url")
        url = str(url).strip() if pd.notna(url) else None
        slug = slug_from_url(url) or slugify(title)
        if slug in seen:  # defensive: slug is the idempotency key, it must be unique
            slug = f"{slug}-{int(rec['id'])}"
        seen.add(slug)

        rate = rec.get("acceptance_rate")
        rows.append({
            "title": title,
            "slug": slug,
            "difficulty": difficulty,
            "topics": map_topics(rec["related_topics"]),
            "description": str(rec["description"]).replace("\r\n", "\n").strip(),
            "url": url,
            "acceptance_rate": float(rate) if pd.notna(rate) else None,
        })
    return rows


def seed(db, rows: list) -> dict:
    """Upsert rows by slug. Returns counts; safe to call any number of times."""
    from models import Problem

    existing = {
        p.slug: p
        for p in db.query(Problem).filter(Problem.slug.in_([r["slug"] for r in rows])).all()
    }
    stats = {"inserted": 0, "updated": 0, "unchanged": 0, "skipped_custom": 0}

    for r in rows:
        p = existing.get(r["slug"])
        if p is None:
            db.add(Problem(source=SOURCE, **r))
            stats["inserted"] += 1
        elif p.source != SOURCE:
            stats["skipped_custom"] += 1  # a hand-added problem owns this slug: leave it alone
        else:
            changed = False
            for key, value in r.items():
                if getattr(p, key) != value:
                    setattr(p, key, value)
                    changed = True
            stats["updated" if changed else "unchanged"] += 1

    db.commit()
    return stats


def main():
    parser = argparse.ArgumentParser(description="Seed problems from the LeetCode CSV (idempotent).")
    parser.add_argument("--csv", default=None, help="path to the dataset CSV")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()

    if not os.getenv("DATABASE_URL"):
        # models.py reads DATABASE_URL (and loads backend/.env)
        from dotenv import load_dotenv
        load_dotenv()

    from sqlalchemy import inspect
    import models

    try:
        rows = load_leetcode_rows(args.csv, args.limit)
    except FileNotFoundError as e:
        sys.exit(str(e))

    if not inspect(models.engine).has_table("problems"):
        sys.exit("The `problems` table does not exist. Run `alembic upgrade head` first.")

    db = models.SessionLocal()
    try:
        stats = seed(db, rows)
        total = db.query(models.Problem).count()
    finally:
        db.close()
    print(f"Seeded from {len(rows)} dataset rows: {stats}. Problems in table: {total}.")


if __name__ == "__main__":
    main()
