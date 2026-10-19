"""
Question banks for the non-DSA interview rounds (Part 9).
DSA questions stay in questions.json (they have hidden tests). SQL and behavioral questions have no
code runner, so the interviewer judges them from the candidate's explanation using the rubric hints below.
"""

ROUNDS = ("dsa", "behavioral", "sql", "resume", "mixed")

BEHAVIORAL = [
    {"id": "beh-1", "title": "Tell me about yourself", "level": "easy",
     "statement": "Tell me about yourself and why you are interested in this role.",
     "follow_ups": ["What is one project you are proudest of, and why?", "Where do you want to be in two years?"]},
    {"id": "beh-2", "title": "Hard bug / failure", "level": "medium",
     "statement": "Tell me about a time something you built did not work, or you made a mistake. What happened and what did you do?",
     "follow_ups": ["What would you do differently now?", "How did you tell your team or mentor about it?"]},
    {"id": "beh-3", "title": "Teamwork and conflict", "level": "medium",
     "statement": "Describe a time you disagreed with a teammate. How did you handle it?",
     "follow_ups": ["What was the outcome?", "What did you learn about working with others?"]},
    {"id": "beh-4", "title": "Learning something new fast", "level": "easy",
     "statement": "Tell me about a time you had to learn a new technology or concept quickly.",
     "follow_ups": ["How did you know you had learned it well enough?", "How did you manage your time?"]},
    {"id": "beh-5", "title": "Leadership / ownership", "level": "hard",
     "statement": "Tell me about a time you took ownership of something nobody asked you to do.",
     "follow_ups": ["How did you measure the impact?", "What resistance did you face?"]},
]
BEHAVIORAL_RUBRIC = ("Judge with STAR: Situation, Task, Action, Result. Reward a concrete example, the candidate's own "
                     "actions ('I', not only 'we'), a measurable result and reflection. Penalise vague or generic answers.")

SQL = [
    {"id": "sql-1", "title": "Second highest salary", "level": "easy",
     "statement": "Table employees(id, name, salary, dept_id). Write a query for the second highest distinct salary.",
     "follow_ups": ["What if there is no second highest salary?", "Can you do it without LIMIT/OFFSET?"]},
    {"id": "sql-2", "title": "Join + group by", "level": "easy",
     "statement": "Tables employees(id, name, dept_id) and departments(id, name). List every department with its employee count, including departments with zero employees.",
     "follow_ups": ["Why LEFT JOIN and not INNER JOIN?", "What happens if you COUNT(*) instead of COUNT(e.id)?"]},
    {"id": "sql-3", "title": "Duplicates", "level": "medium",
     "statement": "Table users(id, email). Find all emails that appear more than once, then explain how you would delete the duplicates but keep one row each.",
     "follow_ups": ["How would an index or UNIQUE constraint prevent this?", "How does your delete behave on a table with 100M rows?"]},
    {"id": "sql-4", "title": "Window function", "level": "medium",
     "statement": "Table orders(id, customer_id, amount, created_at). For each customer return their latest order.",
     "follow_ups": ["Solve it with ROW_NUMBER() and also with a subquery. Which is clearer?", "What if two orders share the same created_at?"]},
    {"id": "sql-5", "title": "Indexes and query plans", "level": "hard",
     "statement": "A query filtering orders by customer_id and sorting by created_at is slow. How do you find out why and how do you fix it?",
     "follow_ups": ["What would the composite index look like and why that column order?", "When can an index make things worse?"]},
]
SQL_RUBRIC = ("Judge correctness of the SQL idea (joins, grouping, NULL handling, edge cases), then complexity/performance "
              "thinking (indexes, scans) and clear explanation. The candidate types SQL as text; do not execute it.")

BANKS = {"behavioral": BEHAVIORAL, "sql": SQL}
RUBRICS = {"behavioral": BEHAVIORAL_RUBRIC, "sql": SQL_RUBRIC}


def pick_from_bank(round_name: str, asked: list, level: str = "") -> dict | None:
    pool = [q for q in BANKS.get(round_name, []) if q["id"] not in asked]
    if level:
        leveled = [q for q in pool if q["level"] == level]
        pool = leveled or pool
    return pool[0] if pool else None
