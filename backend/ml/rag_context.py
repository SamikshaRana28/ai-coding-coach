from ml.recommender import get_similar_questions


def build_similar_questions_context(question_title: str, top_n: int = 3) -> str:
    """
    Retrieves real, embedding-matched similar questions from the existing
    question index (ml/recommender.py) and formats them as grounding
    context for the LLM prompt.

    Why this matters: without this, the LLM guesses plausible-sounding
    but sometimes fake/incorrect "similar question" titles from its own
    training data. This forces it to work off real, retrieved data --
    the retrieval-augmented-generation pattern applied to something we
    already had the retrieval half of.
    """
    similar = get_similar_questions(question_title, top_n=top_n)
    if not similar:
        return "No similar questions found in the index."

    lines = [
        f"- {q['title']} (difficulty: {q['difficulty']}, topics: {q['topics']}, "
        f"similarity: {q['similarity_score']})"
        for q in similar
    ]
    return "\n".join(lines)