def calculate_readiness_score(
    arrays_solved: int,
    graphs_solved: int,
    dp_solved: int,
    trees_solved: int,
    strings_solved: int,
    math_solved: int,
    avg_attempts: float,
    acceptance_rate: float
) -> dict:

    # 1. Volume Score — kitne total problems solve kiye (max 30 points)
    total_solved = (arrays_solved + graphs_solved + dp_solved +
                    trees_solved + strings_solved + math_solved)
    volume_score = min(total_solved / 200 * 30, 30)

    # 2. Variety Score — kitne alag topics cover kiye (max 25 points)
    topics = [arrays_solved, graphs_solved, dp_solved,
              trees_solved, strings_solved, math_solved]
    topics_covered = sum(1 for t in topics if t >= 5)
    variety_score = (topics_covered / 6) * 25

    # 3. Acceptance Rate Score — kitne sahi solve hue (max 25 points)
    acceptance_score = acceptance_rate * 25

    # 4. Efficiency Score — kam attempts mein solve (max 20 points)
    # avg_attempts 1-5 scale hai, kam better hai
    efficiency_score = max(0, (5 - avg_attempts) / 4 * 20)

    # Total score
    total = volume_score + variety_score + acceptance_score + efficiency_score
    total = round(min(total, 100), 1)

    # Level decide karo
    if total >= 80:
        level = "Interview Ready! 🔥"
        message = "Tum FAANG interviews ke liye ready ho!"
    elif total >= 60:
        level = "Almost There 💪"
        message = "Thodi aur practice karo — almost ready!"
    elif total >= 40:
        level = "Developing 📈"
        message = "Sahi raaste pe ho — aur consistency chahiye"
    else:
        level = "Just Starting 🌱"
        message = "Keep going — har expert pehle beginner tha!"

    return {
        "total_score": total,
        "level": level,
        "message": message,
        "breakdown": {
            "volume_score": round(volume_score, 1),
            "variety_score": round(variety_score, 1),
            "acceptance_score": round(acceptance_score, 1),
            "efficiency_score": round(efficiency_score, 1)
        }
    }