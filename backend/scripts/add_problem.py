"""
Add ONE custom problem to the question bank (admin use, run on the server/dev machine).

Usage (from backend/, after `alembic upgrade head`):

    python -m scripts.add_problem \
        --title "Reverse Words in a Sentence" \
        --difficulty Easy \
        --topics "strings,arrays" \
        --description-file ./my_question.txt \
        [--url https://example.com/q]

    # or inline:   --description "Given a string s, ..."

--topics accepts the app's names (arrays, dp, graphs, trees, strings, math, others)
or raw LeetCode names ("Dynamic Programming, Hash Table"); they are mapped for you.
The same thing is available over HTTP as POST /admin/problems (needs ADMIN_TOKEN).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description="Add a custom problem.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--difficulty", required=True, help="Easy | Medium | Hard")
    parser.add_argument("--topics", default="", help="comma separated")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--description", help="problem statement text")
    group.add_argument("--description-file", help="read the problem statement from a file")
    parser.add_argument("--url", default=None, help="optional external link")
    args = parser.parse_args()

    description = (
        Path(args.description_file).read_text(encoding="utf-8")
        if args.description_file else args.description
    )

    from dotenv import load_dotenv
    load_dotenv()
    from sqlalchemy import inspect
    import models
    from problems_service import ProblemExists, create_custom_problem

    if not inspect(models.engine).has_table("problems"):
        sys.exit("The `problems` table does not exist. Run `alembic upgrade head` first.")

    db = models.SessionLocal()
    try:
        problem = create_custom_problem(
            db,
            title=args.title,
            difficulty=args.difficulty,
            topics=[t for t in args.topics.split(",") if t.strip()],
            description=description,
            url=args.url,
        )
    except (ProblemExists, ValueError) as e:
        sys.exit(f"Not added: {e}")
    finally:
        db.close()
    print(f"Added problem #{problem.id} '{problem.title}' ({problem.difficulty}, topics={problem.topics}).")


if __name__ == "__main__":
    main()
