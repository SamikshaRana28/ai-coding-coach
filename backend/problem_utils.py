"""
Pure helpers for the Problems feature (no database / web dependencies).

Maps raw LeetCode topic names (e.g. "Dynamic Programming", "Hash Table") onto the
app's topic taxonomy, so Topic Tracker, Progress and the ML features (which only
know these names) keep working:

    arrays, dp, graphs, trees, strings, math, others
"""
import re
from typing import Iterable, Optional, Union

APP_TOPICS = ("arrays", "dp", "graphs", "trees", "strings", "math", "others")

# Order in which a problem's mapped topics are listed. The FIRST one is the
# problem's "primary topic": it is what gets written to Attempt.topic and
# TopicProgress.topic, so every submission counts towards exactly one topic.
# Specific/structural topics win over generic ones (a "Tree + DFS" problem is a
# trees problem; "Linked List + Math" is math because linked lists have no bucket).
TOPIC_PRIORITY = ("dp", "trees", "graphs", "strings", "arrays", "math", "others")

# Raw (lower-cased) name -> app topic. Anything not listed falls into "others"
# (Hash Table, Backtracking, Linked List, Stack, Queue, Heap, Greedy, Design,
# Binary Search, Two Pointers, Sliding Window, Sort, Recursion, Divide and
# Conquer, ...). Those are techniques that usually co-occur with a main topic.
_DIRECT = {
    "arrays": ("array", "arrays"),
    "dp": ("dynamic programming", "dp", "memoization"),
    "graphs": ("graph", "graphs", "union find", "topological sort"),
    "trees": (
        "tree", "trees", "binary tree", "binary search tree", "trie",
        "binary indexed tree", "segment tree",
    ),
    "strings": ("string", "strings"),
    "math": (
        "math", "bit manipulation", "brainteaser", "random",
        "reservoir sampling", "rejection sampling", "geometry",
        "number theory", "probability",
    ),
    "others": ("other", "others"),
}
_LOOKUP = {raw: app for app, raws in _DIRECT.items() for raw in raws}

# DFS/BFS are traversal techniques: they mean "graphs" on their own, but on a tree
# problem they would only add a misleading second chip, so they are ignored there.
_TRAVERSAL = {"depth-first search", "breadth-first search", "dfs", "bfs"}


def map_topics(raw: Union[None, str, Iterable[str]]) -> list:
    """
    Map raw topic names to app topic names.

    Accepts a comma-separated string ("Array,Hash Table"), a list of names, or
    names that are already app topics ("dp"). Returns a de-duplicated list ordered
    by TOPIC_PRIORITY, never empty ("others" is only used when nothing else maps).
    """
    if raw is None:
        names = []
    elif isinstance(raw, str):
        names = raw.split(",")
    else:
        names = list(raw)
    names = [str(n).strip().lower() for n in names if str(n).strip()]

    has_tree = any(_LOOKUP.get(n) == "trees" for n in names)
    found = set()
    for n in names:
        if n in _TRAVERSAL:
            if not has_tree:
                found.add("graphs")
            continue
        found.add(_LOOKUP.get(n, "others"))

    # "others" is the fallback bucket, not a tag to show next to real topics.
    if len(found) > 1:
        found.discard("others")
    if not found:
        found.add("others")
    return [t for t in TOPIC_PRIORITY if t in found]


def primary_topic(topics: Optional[Iterable[str]]) -> str:
    """The topic a problem counts towards in Attempt / TopicProgress."""
    topics = list(topics or [])
    return topics[0] if topics else "others"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "problem"


def slug_from_url(url: Optional[str]) -> Optional[str]:
    """'https://leetcode.com/problems/two-sum' -> 'two-sum'"""
    if not url:
        return None
    m = re.search(r"/problems/([^/?#]+)", str(url))
    return m.group(1).lower() if m else None


DIFFICULTIES = ("Easy", "Medium", "Hard")


def normalize_difficulty(value: Optional[str]) -> Optional[str]:
    """'easy' / ' MEDIUM ' -> 'Easy' / 'Medium'; None if not a valid difficulty."""
    v = (value or "").strip().capitalize()
    return v if v in DIFFICULTIES else None
