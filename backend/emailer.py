"""
emailer.py - optional reminder emails (Part 6).

Configure ONE of these with environment variables (none set = emails are simply skipped):
    Resend : RESEND_API_KEY + EMAIL_FROM            (e.g. "Coach <coach@yourdomain.com>")
    SMTP   : SMTP_HOST (+ SMTP_PORT, SMTP_USER, SMTP_PASSWORD) + EMAIL_FROM

send_email() never raises: a failing mail server must not break the cron endpoint or the app.
"""
import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Optional

import httpx

log = logging.getLogger(__name__)
TIMEOUT_S = 10.0


def provider() -> Optional[str]:
    if not os.getenv("EMAIL_FROM"):
        return None
    if os.getenv("RESEND_API_KEY"):
        return "resend"
    if os.getenv("SMTP_HOST"):
        return "smtp"
    return None


def email_configured() -> bool:
    return provider() is not None


def send_email(to: str, subject: str, body: str) -> bool:
    """True if the provider accepted the message. False (never an exception) otherwise."""
    kind = provider()
    if kind is None or not to:
        return False
    try:
        if kind == "resend":
            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"},
                json={"from": os.environ["EMAIL_FROM"], "to": [to], "subject": subject, "text": body},
                timeout=TIMEOUT_S,
            )
            ok = resp.status_code < 300
            if not ok:
                log.warning("Resend rejected the email (%s)", resp.status_code)
            return ok

        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = os.environ["EMAIL_FROM"], to, subject
        msg.set_content(body)
        host, port = os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))
        smtp_cls = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
        with smtp_cls(host, port, timeout=TIMEOUT_S) as smtp:
            if port != 465 and os.getenv("SMTP_STARTTLS", "true").lower() not in ("0", "false", "no"):
                smtp.starttls()
            if os.getenv("SMTP_USER"):
                smtp.login(os.environ["SMTP_USER"], os.getenv("SMTP_PASSWORD", ""))
            smtp.send_message(msg)
        return True
    except Exception as e:
        log.warning("sending email failed: %s", type(e).__name__)
        return False
