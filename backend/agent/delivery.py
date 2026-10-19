"""
Communication / body-language feedback (Part 9). PRIVACY: the browser runs MediaPipe locally and
sends ONLY the aggregate numbers below. No video, no images, no landmarks ever reach this server.

Wording matters: this is "eye contact and delivery feedback", NOT a cheating detector. Gaze cannot
tell thinking from cheating, and can be unfair (glasses, disabilities, neurodiversity). The only
integrity numbers we keep are objective events: tab switches, window focus lost, more than one face.
"""
from typing import Annotated

from pydantic import BaseModel, Field

PctF = Annotated[float, Field(ge=0, le=100)]


class DeliveryMetrics(BaseModel):
    model_config = {"extra": "ignore"}          # unknown keys are dropped, never stored

    camera_used: bool = False
    voice_used: bool = False
    duration_seconds: int | None = Field(default=None, ge=0, le=6 * 3600)
    # camera (all optional: a model that failed to load simply reports nothing)
    eye_contact_pct: PctF | None = None
    look_away_count: int | None = Field(default=None, ge=0, le=10000)
    head_stability_pct: PctF | None = None       # 100 = very steady head
    posture_score: PctF | None = None           # 100 = upright, shoulders level
    hand_movement_level: PctF | None = None     # 0 = still, 100 = very busy
    # voice
    filler_words_per_min: float | None = Field(default=None, ge=0, le=200)
    speaking_pace_wpm: float | None = Field(default=None, ge=0, le=400)
    # objective integrity events (counts only)
    tab_switches: int = Field(default=0, ge=0, le=1000)
    focus_lost_events: int = Field(default=0, ge=0, le=1000)
    multiple_faces_events: int = Field(default=0, ge=0, le=1000)


def delivery_report(m: dict | None) -> dict | None:
    """Turn stored aggregate metrics into simple, kind, actionable tips. Pure rules, no LLM."""
    if not m:
        return None
    tips, notes = [], []

    ec = m.get("eye_contact_pct")
    if m.get("camera_used") and ec is not None:
        away = round(100 - ec)
        if ec < 50:
            tips.append(f"You looked away from the screen about {away}% of the time. When you answer, "
                        "try looking at the camera lens, not at your own video tile.")
        elif ec < 70:
            tips.append(f"Eye contact was decent ({round(ec)}%). A bit more time looking at the camera while "
                        "you speak will feel more confident. Glancing away to think is normal.")
        else:
            tips.append(f"Good eye contact ({round(ec)}%). Keep it up.")
    hs = m.get("head_stability_pct")
    if hs is not None and hs < 60:
        tips.append("Your head moved around quite a bit. Try keeping your head steady and use small nods instead.")
    ps = m.get("posture_score")
    if ps is not None and ps < 60:
        tips.append("Sit upright with shoulders level and relaxed. Raise the laptop to eye level if you can.")
    hm = m.get("hand_movement_level")
    if hm is not None:
        if hm > 75:
            tips.append("Lots of hand movement. Natural gestures are good; keep them calm and in frame.")
        elif hm < 5 and m.get("camera_used"):
            tips.append("Your hands were almost still. A few natural gestures can make you look more engaged.")

    fw = m.get("filler_words_per_min")
    if fw is not None:
        if fw > 6:
            tips.append(f"About {round(fw, 1)} filler words per minute (um, uh, you know). Pause silently instead of filling gaps.")
        elif fw > 3:
            tips.append(f"Around {round(fw, 1)} filler words per minute. Slightly high; a short pause works better than 'um'.")
    pace = m.get("speaking_pace_wpm")
    if pace is not None:
        if pace > 180:
            tips.append(f"You spoke fast (~{round(pace)} words/min). Aim for about 120-160 and breathe between points.")
        elif pace < 100:
            tips.append(f"Your pace was slow (~{round(pace)} words/min). That is fine for thinking, but try to keep answers flowing.")
        else:
            tips.append(f"Your speaking pace (~{round(pace)} words/min) was comfortable.")

    integrity = {
        "tab_switches": m.get("tab_switches", 0),
        "focus_lost_events": m.get("focus_lost_events", 0),
        "multiple_faces_events": m.get("multiple_faces_events", 0),
    }
    if any(integrity.values()):
        notes.append("Objective events were recorded (tab switches, window focus lost, or more than one face in view). "
                     "These are only facts about the session, not a judgement about you.")
    if not m.get("camera_used"):
        notes.append("Camera was off, so eye contact and body language were not measured.")
    if not tips:
        tips.append("Not enough delivery data was collected. Try a longer answer with voice or camera on.")

    return {"metrics": {k: v for k, v in m.items() if v is not None}, "tips": tips,
            "integrity": integrity, "notes": notes}
