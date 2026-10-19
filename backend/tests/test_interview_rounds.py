"""Part 9: interview rounds, resume upload, aggregate delivery metrics (privacy-first)."""
import io
import json

import pytest

import agent.interviewer as iv
from agent.delivery import DeliveryMetrics, delivery_report
from agent.tools import tools_for_round


def fake_llm(script):
    state = {"i": 0, "tools": [], "system": []}

    def _call(messages, tools):
        state["tools"].append([t["function"]["name"] for t in tools])
        state["system"].append(messages[0]["content"])
        r = script[min(state["i"], len(script) - 1)]
        state["i"] += 1
        return r

    _call.state = state
    return _call


def say(text):
    return {"content": text, "tool_calls": []}


def call(name, **args):
    return {"content": "", "tool_calls": [{"id": f"call_{name}", "name": name, "args": args}]}


def _pdf_bytes(text="Jane Doe. Built a chat app with FastAPI and React. Two internships in backend development."):
    pytest.importorskip("reportlab")  # pragma: no cover
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, text)
    c.save()
    return buf.getvalue()


# ── Pure logic ─────────────────────────────────────────────────────────────
def test_each_round_only_sees_its_own_tools():
    dsa = {t["function"]["name"] for t in tools_for_round("dsa")}
    beh = {t["function"]["name"] for t in tools_for_round("behavioral")}
    res_no = {t["function"]["name"] for t in tools_for_round("resume", has_resume=False)}
    res_yes = {t["function"]["name"] for t in tools_for_round("resume", has_resume=True)}
    assert "run_tests" in dsa and "pick_round_question" not in dsa
    assert "run_tests" not in beh and "pick_round_question" in beh
    assert "read_resume" not in res_no and "read_resume" in res_yes


def test_metrics_are_validated_and_unknown_keys_dropped():
    m = DeliveryMetrics(**{"camera_used": True, "eye_contact_pct": 62.5, "video_frame": "BASE64...", "tab_switches": 2})
    dumped = m.model_dump()
    assert "video_frame" not in dumped and dumped["eye_contact_pct"] == 62.5
    with pytest.raises(Exception):
        DeliveryMetrics(eye_contact_pct=140)          # out of range
    with pytest.raises(Exception):
        DeliveryMetrics(tab_switches=-1)


def test_delivery_report_tips_and_wording():
    rep = delivery_report({"camera_used": True, "eye_contact_pct": 62, "filler_words_per_min": 7.5,
                           "speaking_pace_wpm": 190, "tab_switches": 1})
    text = " ".join(rep["tips"] + rep["notes"]).lower()
    assert "filler" in text and "fast" in text
    assert "cheat" not in text                        # delivery feedback, never an accusation
    assert rep["integrity"]["tab_switches"] == 1
    low = delivery_report({"camera_used": True, "eye_contact_pct": 40})
    assert "38%" not in low["tips"][0] and "60%" in low["tips"][0]
    assert delivery_report(None) is None


# ── API ────────────────────────────────────────────────────────────────────
def test_behavioral_round_flow_and_scorecard_labels(client, make_user, monkeypatch):
    _, h = make_user("beh@example.com")
    fake = fake_llm([
        call("pick_round_question", round="behavioral"), say("Tell me about a time you made a mistake."),
        call("save_scorecard", approach=4, complexity=3, edge_cases=3, communication=5, summary="Clear STAR answer"),
        say("Thanks!"),
    ])
    monkeypatch.setattr(iv, "llm_call", fake)
    r = client.post("/interview/start", json={"round": "behavioral", "topic": "arrays"}, headers=h).json()
    assert r["round"] == "behavioral" and "mistake" in r["reply"]
    assert "run_tests" not in fake.state["tools"][0]
    assert "Behavioral" in fake.state["system"][0]
    client.post(f"/interview/{r['session_id']}/answer", json={"answer": "In my project I ..."}, headers=h)
    sc = client.get(f"/interview/{r['session_id']}/scorecard", headers=h).json()
    assert sc["round"] == "behavioral" and sc["total"] == 15 and sc["delivery"] is None


def test_resume_round_needs_resume_and_wipes_it_when_done(client, make_user, monkeypatch, db):
    from models import InterviewSession
    _, h = make_user("res@example.com")
    assert client.post("/interview/start", json={"round": "resume"}, headers=h).status_code == 422

    monkeypatch.setattr(iv, "llm_call", fake_llm([
        call("read_resume"), say("I see you built a chat app. Why FastAPI?"),
        call("save_scorecard", approach=3, complexity=3, edge_cases=3, communication=3), say("Bye"),
    ]))
    resume = "Jane Doe. Built a chat app with FastAPI and React. Two internships in backend development."
    r = client.post("/interview/start", json={"round": "resume", "resume_text": resume}, headers=h).json()
    sid = r["session_id"]
    assert "FastAPI" in r["reply"]
    assert client.get(f"/interview/{sid}", headers=h).json()["has_resume"] is True
    client.post(f"/interview/{sid}/answer", json={"answer": "Because it is fast"}, headers=h)
    db.expire_all()
    assert db.get(InterviewSession, sid).resume_text is None            # wiped once the interview ended


def test_resume_extract_rejects_non_pdf_and_requires_login(client, make_user):
    _, h = make_user("up@example.com")
    files = {"file": ("cv.pdf", b"not a pdf at all", "application/pdf")}
    assert client.post("/interview/resume/extract", files=files).status_code == 401
    assert client.post("/interview/resume/extract", files=files, headers=h).status_code == 415
    big = {"file": ("cv.pdf", b"%PDF" + b"0" * (3 * 1024 * 1024 + 10), "application/pdf")}
    assert client.post("/interview/resume/extract", files=big, headers=h).status_code == 413


def test_resume_extract_reads_text(client, make_user):
    pytest.importorskip("reportlab")
    _, h = make_user("pdf@example.com")
    files = {"file": ("cv.pdf", _pdf_bytes(), "application/pdf")}
    r = client.post("/interview/resume/extract", files=files, headers=h)
    assert r.status_code == 200 and "FastAPI" in r.json()["resume_text"]


def test_metrics_saved_shown_in_scorecard_and_private(client, make_user, monkeypatch):
    _, ha = make_user("ma@example.com")
    _, hb = make_user("mb@example.com")
    monkeypatch.setattr(iv, "llm_call", fake_llm([
        say("Q1"), call("save_scorecard", approach=4, complexity=4, edge_cases=4, communication=4), say("Bye")]))
    sid = client.post("/interview/start", json={"round": "dsa"}, headers=ha).json()["session_id"]
    client.post(f"/interview/{sid}/answer", json={"answer": "done"}, headers=ha)

    body = {"camera_used": True, "eye_contact_pct": 55, "look_away_count": 9, "filler_words_per_min": 4.2,
            "tab_switches": 1, "frame": "data:image/png;base64,AAAA"}
    assert client.post(f"/interview/{sid}/metrics", json=body, headers=hb).status_code == 404   # not yours
    assert client.post(f"/interview/{sid}/metrics", json=body, headers=ha).status_code == 200
    bad = client.post(f"/interview/{sid}/metrics", json={"eye_contact_pct": 500}, headers=ha)
    assert bad.status_code == 422

    sc = client.get(f"/interview/{sid}/scorecard", headers=ha).json()
    d = sc["delivery"]
    assert d["metrics"]["eye_contact_pct"] == 55 and d["integrity"]["tab_switches"] == 1
    assert "frame" not in json.dumps(d)                                # nothing image-like is ever stored
