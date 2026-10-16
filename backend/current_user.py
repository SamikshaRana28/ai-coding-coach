"""
current_user.py - "who is the logged-in user?" for the Coach endpoints.

PLACEHOLDER: this reads an X-User-Id header (default 1) because this codebase had no
login when it was written. That is NOT secure - anyone could send someone else's id.
Replace get_user_id with your Part 1 auth dependency (the one that reads the JWT /
session and returns the logged-in user's id) BEFORE you deploy, e.g. in coach_router.py:

    from auth import get_current_user_id as get_user_id
"""
from typing import Optional

from fastapi import Header


def get_user_id(x_user_id: Optional[int] = Header(default=None)) -> int:
    return x_user_id if x_user_id and x_user_id > 0 else 1
