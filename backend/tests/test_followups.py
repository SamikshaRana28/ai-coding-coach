"""Part 6 tests: check-in, weekly review, notifications, settings, cron (time frozen, LLM faked)."""
import json
from types import SimpleNamespace

import pytest

from tests.conftest import give_stats
from tests.test_plan import generate, pl, tasks_of  # noqa: F401  (pl fixture = api + question bank + frozen time)


def checkin(api, headers=None):
    return api.client.get("/coach/checkin/today", headers=headers or {}).json()


def kinds(c):
    return [m["kind"] for m in c["messages"]]


def finish_all_today(api):
    for t in api.client.get("/tasks/today").json()["tasks"]:
        api.client.post(f"/tasks/{t['id']}/complete")


# ── daily check-in (lazy, in app) ─────────────────────────────────────────────
def test_followup_endpoints_need_login(api):
    from fastapi.testclient import TestClient

    anon = TestClient(api.main.app)
    for method, path in [("get", "/coach/checkin/today"), ("post", "/coach/checkin"), ("get", "/notifications"),
                         ("post", "/notifications/read"), ("get", "/settings"), ("put", "/settings"),
                         ("post", "/plan/weekly-review"), ("get", "/plan/weekly-review"),
                         ("post", "/plan/weekly-review/confirm"), ("delete", "/plan/weekly-review")]:
        assert getattr(anon, method)(path).status_code == 401, path


def test_no_plan_greeting_offers_to_make_one(pl):
    c = checkin(pl)
    assert kinds(c) == ["no_plan"] and c["messages"][0]["actions"][0]["id"] == "generate_plan"
    assert "User One" not in c["messages"][0]["text"] and "Hi User" in c["messages"][0]["text"]
    assert c["needs_attention"] is True


def test_morning_greeting_lists_todays_tasks_and_the_streak(pl):
    generate(pl)
    c = checkin(pl)                                              # Monday 09:30 IST
    assert c["part_of_day"] == "morning" and kinds(c) == ["morning"]
    text = c["messages"][0]["text"]
    titles = [t["title"] for t in pl.client.get("/tasks/today").json()["tasks"]]
    assert text.startswith("Good morning, User!") and all(t in text for t in titles)
    assert "Finish one task today to start a streak" in text
    pl.client.post(f"/tasks/{pl.client.get('/tasks/today').json()['tasks'][0]['id']}/complete")
    pl.ctl.advance(days=1)
    pl.client.post(f"/tasks/{pl.client.get('/tasks/today').json()['tasks'][0]['id']}/complete")
    pl.ctl.advance(days=1)
    assert "Your streak is 2 days." in checkin(pl)["messages"][-1]["text"]


def test_missing_yesterday_offers_to_reschedule_or_lighten(pl, ctl):
    generate(pl)
    first = pl.client.get("/tasks/today").json()["tasks"]
    pl.client.post(f"/tasks/{first[0]['id']}/complete")           # 1 done, the rest missed
    ctl.advance(days=1)                                           # Tuesday morning
    c = checkin(pl)
    assert kinds(c)[0] == "missed_yesterday"
    m = c["messages"][0]
    assert f"You missed yesterday's tasks (1/{len(first)} done)." in m["text"]
    assert "move them to today or lighten the plan" in m["text"]
    assert [a["id"] for a in m["actions"]] == ["reschedule", "lighten"]
    assert pl.client.post("/tasks/reschedule").json()["moved"] == len(first) - 1
    assert "missed_yesterday" not in kinds(checkin(pl))           # handled


def test_evening_reminder_with_pending_tasks(pl, ctl):
    generate(pl)
    ctl.set(2026, 10, 19, 15, 30)                                 # 21:00 IST
    c = checkin(pl)
    n = len(pl.client.get("/tasks/today").json()["tasks"])
    assert c["part_of_day"] == "evening" and "evening_pending" in kinds(c)
    text = next(m["text"] for m in c["messages"] if m["kind"] == "evening_pending")
    assert f"You still have {n} tasks pending today. Even one keeps your streak alive." in text
    pl.client.post(f"/tasks/{pl.client.get('/tasks/today').json()['tasks'][0]['id']}/complete")
    text = next(m["text"] for m in checkin(pl)["messages"] if m["kind"] == "evening_pending")
    assert "already safe for today" in text
    finish_all_today(pl)
    assert kinds(checkin(pl)) == ["all_done"]


def test_midday_welcome_back(pl, ctl):
    generate(pl)
    ctl.set(2026, 10, 19, 8, 0)                                   # 13:30 IST
    c = checkin(pl)
    assert kinds(c) == ["welcome_back"] and "0 of" in c["messages"][0]["text"]


def test_checkin_is_per_user_and_data_based(pl):
    generate(pl)
    other = checkin(pl, pl.h2)
    assert kinds(other) == ["no_plan"]


# ── saving a check-in ─────────────────────────────────────────────────────────
def test_checkin_question_appears_in_the_evening_and_saves_once_a_day(pl, ctl):
    generate(pl)
    assert checkin(pl)["ask_checkin"] is False                    # morning: not asked yet
    ctl.set(2026, 10, 19, 14, 0)                                  # 19:30 IST
    c = checkin(pl)
    assert c["ask_checkin"] is True and c["questions"] == ["How was your day?", "Did you follow the schedule?"]

    r = pl.client.post("/coach/checkin", json={"mood": 4, "note": "went fine"}).json()
    assert r["checkin"]["mood"] == 4 and r["suggest_lighter"] is False and "Even one small task" in r["reply"]
    c = checkin(pl)
    assert c["ask_checkin"] is False and c["checkin_today"]["note"] == "went fine"

    pl.client.post("/coach/checkin", json={"mood": 5})            # saving again replaces today's row
    from models import CheckIn

    db = pl.Session()
    rows = db.query(CheckIn).filter(CheckIn.user_id == 1).all()
    db.close()
    assert len(rows) == 1 and rows[0].mood == 5 and rows[0].note is None


def test_tired_or_sick_student_is_offered_a_lighter_plan(pl):
    generate(pl)
    r = pl.client.post("/coach/checkin", json={"mood": 2, "note": "I was sick today"}).json()
    assert r["suggest_lighter"] is True and r["actions"][0]["id"] == "lighten"
    assert "lighter plan" in r["reply"]
    r = pl.client.post("/coach/checkin", json={"note": "I am so overwhelmed"}).json()
    assert r["suggest_lighter"] is True
    r = pl.client.post("/coach/checkin", json={"mood": 5, "note": "great day"}).json()
    assert r["suggest_lighter"] is False


def test_checkin_validation(pl):
    assert pl.client.post("/coach/checkin", json={}).status_code == 422
    assert pl.client.post("/coach/checkin", json={"mood": 6}).status_code == 422
    assert pl.client.post("/coach/checkin", json={"mood": 0}).status_code == 422
    assert pl.client.post("/coach/checkin", json={"note": "x" * 501}).status_code == 422
    assert pl.client.post("/coach/checkin", json={"note": "   "}).status_code == 422


def test_lighter_plan_via_generate_after_checkin(pl):
    generate(pl)
    plan = generate(pl, minutes_per_day=30).json()                # what the "Lighten my plan" button sends
    assert all(len(d["tasks"]) == 2 for d in plan["days"])


def test_coach_chat_gets_the_checkin_as_context(pl, monkeypatch):
    import coach_router

    seen = {}

    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    seen["messages"] = kw["messages"]
                    msg = SimpleNamespace(content="Take it easy today.", tool_calls=None)
                    return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")])

    monkeypatch.setattr(coach_router, "get_client", lambda: FakeClient)
    monkeypatch.setattr(coach_router, "limiter", coach_router.RateLimiter(100))
    pl.client.post("/coach/checkin", json={"mood": 1, "note": "feeling sick"})
    r = pl.client.post("/coach/chat", json={"message": "hi"})
    assert r.status_code == 200, r.text
    last_user = next(m for m in reversed(seen["messages"]) if m["role"] == "user")["content"]
    assert "Today's check-in: mood 1/5" in last_user and "feeling sick" in last_user
    assert "offer a lighter plan" in last_user


# ── weekly review ─────────────────────────────────────────────────────────────
def start_review(api):
    return api.client.post("/plan/weekly-review")


def test_weekly_review_needs_a_plan(pl):
    r = start_review(pl)
    assert r.status_code == 409 and "no study plan" in r.json()["detail"].lower()
    assert pl.client.post("/plan/weekly-review/confirm").status_code == 409
    assert pl.client.get("/plan/weekly-review").json() == {"review": None, "plan": None}


def test_first_open_of_a_new_week_offers_the_review(pl, ctl):
    generate(pl)
    assert "weekly_review" not in kinds(checkin(pl))
    ctl.advance(days=6)
    assert "weekly_review" not in kinds(checkin(pl))              # the plan's last day
    ctl.advance(days=1)                                           # first open of the next week
    c = checkin(pl)
    assert kinds(c)[0] == "weekly_review" and c["messages"][0]["actions"][0]["id"] == "weekly_review"
    assert "morning" not in kinds(c) and "missed_yesterday" not in kinds(c)


def test_weekly_review_summarises_the_week_and_proposes_next_week(pl, ctl):
    plan = generate(pl).json()
    # a good week: do all of Monday, solve one problem on Wednesday
    finish_all_today(pl)
    ctl.advance(days=2)
    wed = next(t for t in pl.client.get("/tasks/today").json()["tasks"] if t["kind"] == "problem")
    pl.client.post(f"/problems/{wed['problem_id']}/submit", json={"code": "x = 1"})
    ctl.advance(days=5)                                           # next Monday

    r = start_review(pl).json()
    review, proposed = r["review"], r["plan"]
    total = len(tasks_of(plan))
    assert review["tasks"]["total"] == total and review["tasks"]["done"] >= 4
    assert review["solved_total"] == 1 and review["active_days"] == 2
    assert review["period"] == {"start": "2026-10-19", "end": "2026-10-25"}
    assert review["improved"] and isinstance(review["needs_work"], list)
    assert str(review["tasks"]["done"]) in review["narrative"]
    assert proposed["status"] == "proposed" and proposed["week_start"] == "2026-10-26"
    assert len(proposed["days"]) == 7 and all(len(d["tasks"]) >= 2 for d in proposed["days"])

    # nothing is replaced until the student confirms
    cur = pl.client.get("/plan/current").json()["plan"]
    assert cur["id"] == plan["id"] and cur["status"] == "active"
    assert pl.client.get("/plan/weekly-review").json()["plan"]["id"] == proposed["id"]
    assert "weekly_review" in kinds(checkin(pl))

    confirmed = pl.client.post("/plan/weekly-review/confirm").json()["plan"]
    assert confirmed["id"] == proposed["id"] and confirmed["status"] == "active"
    assert pl.client.get("/plan/current").json()["plan"]["id"] == proposed["id"]
    from models import StudyPlan

    db = pl.Session()
    assert db.get(StudyPlan, plan["id"]).status == "archived"
    db.close()
    assert pl.client.get("/plan/weekly-review").json()["plan"] is None
    assert pl.client.get("/tasks/today").json()["date"] == "2026-10-26"


def test_a_missed_week_gives_a_lighter_next_week_and_carries_topics(pl, ctl):
    generate(pl)
    ctl.advance(days=7)                                           # nothing was done
    r = start_review(pl).json()
    assert r["review"]["lighter"] is True and r["review"]["tasks"]["percent"] == 0
    assert any("Only 0 of" in w for w in r["review"]["needs_work"])
    assert all(len(d["tasks"]) == 2 for d in r["plan"]["days"])                    # lighter: 2 a day
    assert "lighter" in r["plan"]["summary"].lower()
    assert r["review"]["carry_topics"]                                             # topics with no progress come first
    assert r["plan"]["focus_topics"][0]["topic"] == r["review"]["carry_topics"][0]
    assert "no progress here last week" in r["plan"]["focus_topics"][0]["reason"]


def test_discard_the_proposal_keeps_the_current_plan(pl, ctl):
    plan = generate(pl).json()
    ctl.advance(days=7)
    start_review(pl)
    assert pl.client.delete("/plan/weekly-review").json() == {"discarded": True}
    assert pl.client.delete("/plan/weekly-review").json() == {"discarded": False}
    assert pl.client.get("/plan/current").json()["plan"]["id"] == plan["id"]
    from models import DailyTask

    db = pl.Session()
    assert db.query(DailyTask).filter(DailyTask.plan_id != plan["id"]).count() == 0     # its tasks are gone too
    db.close()


def test_starting_the_review_twice_replaces_the_proposal(pl, ctl):
    generate(pl)
    ctl.advance(days=7)
    start_review(pl)
    b = start_review(pl).json()["plan"]["id"]
    from models import DailyTask, StudyPlan

    db = pl.Session()
    assert [p.id for p in db.query(StudyPlan).filter(StudyPlan.status == "proposed")] == [b]   # only one proposal exists
    assert db.query(DailyTask).filter(DailyTask.plan_id == b).count() >= 14                     # no leftover tasks doubled
    db.close()


def test_weekly_review_is_per_user(pl, ctl):
    generate(pl)
    ctl.advance(days=7)
    start_review(pl)
    assert pl.client.get("/plan/weekly-review", headers=pl.h2).json() == {"review": None, "plan": None}
    assert pl.client.post("/plan/weekly-review/confirm", headers=pl.h2).status_code == 409


# ── notifications + settings ──────────────────────────────────────────────────
def test_notifications_list_and_mark_read(pl):
    from models import Notification

    db = pl.Session()
    db.add_all([Notification(user_id=1, type="nudge", message="one"), Notification(user_id=1, type="nudge", message="two"),
                Notification(user_id=2, type="nudge", message="not mine")])
    db.commit()
    db.close()
    n = pl.client.get("/notifications").json()
    assert n["unread"] == 2 and [i["message"] for i in n["items"]] == ["two", "one"]
    assert checkin(pl)["unread_notifications"] == 2 and checkin(pl)["needs_attention"] is True
    assert pl.client.post("/notifications/read").json() == {"marked_read": 2}
    assert pl.client.get("/notifications").json()["unread"] == 0
    assert pl.client.get("/notifications", headers=pl.h2).json()["unread"] == 1


def test_settings_default_off_and_toggle(pl):
    s = pl.client.get("/settings").json()
    assert s["notify_email"] is False and s["email_available"] is False and s["email"] == "one@example.com"
    assert pl.client.put("/settings", json={"notify_email": True}).json()["notify_email"] is True
    assert pl.client.get("/settings").json()["notify_email"] is True
    assert pl.client.get("/settings", headers=pl.h2).json()["notify_email"] is False       # per user
    assert pl.client.put("/settings", json={"notify_email": "maybe"}).status_code == 422
    assert pl.client.put("/settings", json={}).status_code == 422


# ── cron ──────────────────────────────────────────────────────────────────────
SECRET = "cron-test-secret"


@pytest.fixture()
def cron(pl, monkeypatch):
    monkeypatch.setenv("CRON_SECRET", SECRET)
    for var in ("RESEND_API_KEY", "EMAIL_FROM", "SMTP_HOST"):
        monkeypatch.delenv(var, raising=False)
    pl.sent = []

    def fake_send(to, subject, body):
        pl.sent.append((to, subject, body))
        return True

    monkeypatch.setattr("emailer.send_email", fake_send)

    def call(slot="morning", secret=SECRET):
        headers = {"X-Cron-Secret": secret} if secret is not None else {}
        return pl.client.post(f"/internal/cron/daily-nudges?slot={slot}", headers=headers)

    pl.cron = call
    return pl


def test_cron_rejects_requests_without_the_secret(cron, monkeypatch):
    assert cron.cron(secret=None).status_code == 403
    assert cron.cron(secret="wrong").status_code == 403
    assert cron.cron(secret="").status_code == 403
    assert cron.client.post("/internal/cron/daily-nudges", headers=cron.h1).status_code == 403   # a user's JWT is not enough
    monkeypatch.delenv("CRON_SECRET")
    assert cron.cron().status_code == 503                         # disabled until CRON_SECRET is configured
    assert cron.cron(secret=None).status_code == 503


def test_cron_creates_in_app_notifications_without_any_email_setup(cron):
    generate(cron)
    generate(cron, headers=cron.h2)
    r = cron.cron("morning").json()
    assert r["users_checked"] == 2 and r["notifications_created"] == 2
    assert r["emails_sent"] == 0 and r["email_configured"] is False
    n = cron.client.get("/notifications").json()
    assert n["unread"] == 1 and n["items"][0]["type"] == "nudge" and "Good morning!" in n["items"][0]["message"]
    assert cron.sent == []


def test_cron_is_idempotent_per_slot_and_day(cron, ctl):
    generate(cron)
    assert cron.cron("morning").json()["notifications_created"] == 1
    assert cron.cron("morning").json()["notifications_created"] == 0     # a retry never doubles the nudge
    ctl.advance(days=1)
    assert cron.cron("morning").json()["notifications_created"] == 1     # a new day is a new nudge


def test_cron_skips_users_without_pending_tasks_and_without_plans(cron):
    generate(cron)
    finish_all_today(cron)
    r = cron.cron("morning").json()
    assert r["users_checked"] == 1 and r["notifications_created"] == 0     # user 2 has no plan, user 1 finished
    assert cron.client.get("/notifications").json()["unread"] == 0


def test_cron_evening_is_a_streak_save_reminder(cron, ctl):
    generate(cron)
    cron.client.post(f"/tasks/{cron.client.get('/tasks/today').json()['tasks'][0]['id']}/complete")   # Monday: streak 1
    ctl.advance(days=1)
    ctl.set(2026, 10, 20, 15, 0)                                  # Tuesday 20:30 IST, nothing done yet today
    assert cron.cron("evening").json()["notifications_created"] == 1
    msg = cron.client.get("/notifications").json()["items"][0]["message"]
    assert msg == "Save your 1 day streak: finish just one task today."
    # once the streak is safe for today, the evening nudge is not sent
    cron.client.post(f"/tasks/{cron.client.get('/tasks/today').json()['tasks'][0]['id']}/complete")
    ctl.advance(days=1)
    ctl.set(2026, 10, 21, 3, 0)
    cron.client.post(f"/tasks/{cron.client.get('/tasks/today').json()['tasks'][0]['id']}/complete")
    ctl.set(2026, 10, 21, 15, 0)
    assert cron.cron("evening").json()["notifications_created"] == 0


def test_cron_morning_announces_the_weekly_review_once(cron, ctl):
    generate(cron)
    ctl.advance(days=7)
    assert cron.cron("morning").json()["notifications_created"] == 1
    item = cron.client.get("/notifications").json()["items"][0]
    assert item["type"] == "weekly_review" and "weekly review" in item["message"]
    ctl.advance(days=1)
    assert cron.cron("morning").json()["notifications_created"] == 0      # same plan: announced once
    assert cron.cron("evening").json()["notifications_created"] == 0


def test_cron_emails_only_opted_in_users_when_a_provider_is_configured(cron, monkeypatch):
    monkeypatch.setenv("EMAIL_FROM", "Coach <coach@example.com>")
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    generate(cron)
    generate(cron, headers=cron.h2)
    cron.client.put("/settings", json={"notify_email": True})              # only user 1 opts in
    r = cron.cron("morning").json()
    assert r["email_configured"] is True and r["notifications_created"] == 2
    assert r["emails_sent"] == 1 and r["emails_failed"] == 0
    assert [to for to, _, _ in cron.sent] == ["one@example.com"]
    assert "Good morning!" in cron.sent[0][2] and cron.sent[0][1] == "Today's study tasks"
    assert cron.cron("morning").json()["emails_sent"] == 0                 # the retry sends no second email


def test_a_failing_email_provider_never_breaks_the_cron_endpoint(cron, monkeypatch):
    monkeypatch.setenv("EMAIL_FROM", "coach@example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.invalid")
    monkeypatch.setattr("emailer.send_email", lambda *a: False)
    generate(cron)
    cron.client.put("/settings", json={"notify_email": True})
    r = cron.cron("morning")
    assert r.status_code == 200 and r.json()["emails_failed"] == 1 and r.json()["notifications_created"] == 1


def test_cron_slot_must_be_morning_or_evening(cron):
    assert cron.client.post("/internal/cron/daily-nudges?slot=noon", headers={"X-Cron-Secret": SECRET}).status_code == 422


# ── emailer itself ────────────────────────────────────────────────────────────
def test_emailer_without_config_returns_false_and_never_raises(monkeypatch):
    import emailer

    for var in ("RESEND_API_KEY", "EMAIL_FROM", "SMTP_HOST"):
        monkeypatch.delenv(var, raising=False)
    assert emailer.email_configured() is False
    assert emailer.send_email("a@b.com", "s", "b") is False


def test_emailer_resend_success_and_failure(monkeypatch):
    import emailer

    monkeypatch.setenv("EMAIL_FROM", "c@example.com")
    monkeypatch.setenv("RESEND_API_KEY", "re_x")
    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, json))
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(emailer.httpx, "post", fake_post)
    assert emailer.send_email("a@b.com", "Hi", "Body") is True
    assert calls[0][0] == "https://api.resend.com/emails" and calls[0][1]["to"] == ["a@b.com"]
    monkeypatch.setattr(emailer.httpx, "post", lambda *a, **k: SimpleNamespace(status_code=422))
    assert emailer.send_email("a@b.com", "Hi", "Body") is False
    monkeypatch.setattr(emailer.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network")))
    assert emailer.send_email("a@b.com", "Hi", "Body") is False


def test_emailer_smtp(monkeypatch):
    import emailer

    monkeypatch.setenv("EMAIL_FROM", "c@example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    log = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            log.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            log.append("starttls")

        def login(self, u, p):
            log.append(("login", u))

        def send_message(self, msg):
            log.append(("send", msg["To"], msg["Subject"]))

    monkeypatch.setattr(emailer.smtplib, "SMTP", FakeSMTP)
    assert emailer.send_email("a@b.com", "Hello", "Body") is True
    assert log == [("connect", "smtp.example.com", 587), "starttls", ("login", "u"), ("send", "a@b.com", "Hello")]
