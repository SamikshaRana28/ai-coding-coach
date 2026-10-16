"""Pure-logic tests (no DB / web framework needed)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from problem_utils import (  # noqa: E402
    APP_TOPICS, map_topics, normalize_difficulty, primary_topic, slug_from_url, slugify,
)
from scripts.seed_problems import load_leetcode_rows  # noqa: E402


def test_topic_mapping_cases():
    cases = {
        "Array,Hash Table": ["arrays"],
        "Linked List,Math,Recursion": ["math"],
        "Dynamic Programming,String": ["dp", "strings"],
        "Tree,Depth-first Search,Breadth-first Search": ["trees"],            # DFS/BFS ignored on trees
        "Depth-first Search,Breadth-first Search,Union Find": ["graphs"],
        "Hash Table": ["others"],
        "Binary Search,Two Pointers": ["others"],
        "Hash Table,Two Pointers,String,Sliding Window": ["strings"],        # 'others' dropped next to a real topic
        "": ["others"],
    }
    for raw, expected in cases.items():
        assert map_topics(raw) == expected, raw
    assert map_topics(None) == ["others"]


def test_topic_mapping_accepts_lists_and_app_names():
    assert map_topics(["dp", "Arrays"]) == ["dp", "arrays"]
    assert map_topics(["Graph"]) == ["graphs"]
    assert map_topics(["linked lists"]) == ["others"]       # unknown -> others


def test_topic_mapping_output_is_always_valid_and_ordered():
    out = map_topics("Math,String,Array,Dynamic Programming,Graph,Tree")
    assert out == ["dp", "trees", "graphs", "strings", "arrays", "math"]
    assert set(out) <= set(APP_TOPICS)


def test_primary_topic():
    assert primary_topic(["dp", "strings"]) == "dp"
    assert primary_topic([]) == "others"
    assert primary_topic(None) == "others"


def test_slug_helpers():
    assert slug_from_url("https://leetcode.com/problems/two-sum") == "two-sum"
    assert slug_from_url("https://leetcode.com/problems/two-sum/?x=1") == "two-sum"
    assert slug_from_url(None) is None
    assert slugify("Reverse Words (v2)!") == "reverse-words-v2"
    assert slugify("???") == "problem"


def test_normalize_difficulty():
    assert normalize_difficulty("easy") == "Easy"
    assert normalize_difficulty(" HARD ") == "Hard"
    assert normalize_difficulty("insane") is None
    assert normalize_difficulty(None) is None


def test_csv_loader_gives_the_500_recommender_questions():
    rows = load_leetcode_rows()
    assert len(rows) == 500
    assert len({r["slug"] for r in rows}) == 500
    assert all(r["difficulty"] in ("Easy", "Medium", "Hard") for r in rows)
    assert all(r["topics"] and set(r["topics"]) <= set(APP_TOPICS) for r in rows)
    assert all(r["description"] for r in rows)

    # must be exactly the questions the recommender indexes (same order)
    import pandas as pd
    pkl = Path(__file__).resolve().parents[1] / "ml" / "questions_df.pkl"
    try:
        recommender = pd.read_pickle(pkl)
    except Exception as e:  # pickle written by a different pandas version
        pytest.skip(f"cannot read {pkl.name}: {e}")
    assert [r["title"] for r in rows] == recommender["title"].tolist()
