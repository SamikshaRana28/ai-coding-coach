"""
Authentication for AI Coding Coach (email + password, JWT bearer tokens).

Rules this module enforces:
  * Passwords are hashed with argon2id and never stored/logged/returned.
  * user identity ALWAYS comes from the verified JWT (get_current_user),
    never from the request body, query string or URL.
  * Login failures use one generic message so accounts can't be enumerated.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from slowapi import Limiter
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import User, get_db

logger = logging.getLogger("auth")

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = int(os.getenv("JWT_EXPIRE_DAYS", "7"))
MIN_JWT_SECRET_LENGTH = 32
DEFAULT_TIMEZONE = "Asia/Kolkata"
AUTH_RATE_LIMIT = os.getenv("AUTH_RATE_LIMIT", "10/minute")

GENERIC_LOGIN_ERROR = "Invalid email or password"


# ── Rate limiting ──────────────────────────────────────────────────────────
def _client_ip(request: Request) -> str:
    """
    Client IP used as the rate-limit key.

    Behind a reverse proxy (Render) every request appears to come from the
    proxy, so all users would share one bucket. Set TRUSTED_PROXY_HOPS=N to
    read the client IP from X-Forwarded-For, counting N entries from the
    RIGHT (entries added by YOUR proxies). Default 0 = ignore the header,
    because a client can forge it.
    """
    try:
        hops = int(os.getenv("TRUSTED_PROXY_HOPS", "0") or 0)
    except ValueError:
        hops = 0
    if hops > 0:
        forwarded = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return request.client.host if request.client else "unknown"


limiter = Limiter(
    key_func=_client_ip,
    enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() not in ("0", "false", "no"),
)


# ── Passwords ──────────────────────────────────────────────────────────────
_hasher = PasswordHasher()
# Verified against when the email is unknown, so "no such user" and "wrong
# password" take about the same time.
_DUMMY_HASH = _hasher.hash("timing-equalisation-only")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# ── JWT ────────────────────────────────────────────────────────────────────
def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "")
    if len(secret) < MIN_JWT_SECRET_LENGTH:
        # Fail only the auth routes (not the whole app) if the server is misconfigured.
        logger.error("JWT_SECRET is missing or shorter than %d characters", MIN_JWT_SECRET_LENGTH)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured on the server",
        )
    return secret


def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_access_token(token: str) -> int:
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, ValueError, TypeError):
        raise _unauthorized("Invalid or expired token")


# ── Dependencies ───────────────────────────────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """The ONLY source of user identity for protected endpoints."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized("Invalid or expired token")
    return user


def require_path_user(user_id: int, current_user: User = Depends(get_current_user)) -> User:
    """
    For legacy URLs shaped like /something/{user_id}: keep the URL working, but
    the path id must match the logged-in user, otherwise 403.
    """
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own data",
        )
    return current_user


# ── Schemas ────────────────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: Optional[str] = Field(default=None, max_length=100)
    first_name: Optional[str] = Field(default=None, max_length=50)
    last_name: Optional[str] = Field(default=None, max_length=50)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.strip().lower()

    @model_validator(mode="after")
    def _fill_names(self):
        def clean(value: Optional[str]) -> Optional[str]:
            value = " ".join((value or "").split())
            return value or None

        self.name = clean(self.name)
        self.first_name = clean(self.first_name)
        self.last_name = clean(self.last_name)

        if not self.name:
            self.name = " ".join(p for p in (self.first_name, self.last_name) if p) or None
        if not self.name:
            raise ValueError("name is required")
        if not self.first_name:
            parts = self.name.split(" ", 1)
            self.first_name = parts[0]
            if not self.last_name and len(parts) > 1:
                self.last_name = parts[1]
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    # No min-length here on purpose: don't reveal the password policy on login.
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.strip().lower()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    timezone: Optional[str] = None
    created_at: Optional[datetime] = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ── Router ─────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/auth", tags=["auth"])


def _find_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(func.lower(User.email) == email).first()


@router.post("/signup", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(AUTH_RATE_LIMIT)
def signup(request: Request, body: SignupRequest, db: Session = Depends(get_db)):
    if _find_user_by_email(db, body.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        name=body.name,
        first_name=body.first_name,
        last_name=body.last_name,
        timezone=DEFAULT_TIMEZONE,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    db.refresh(user)

    logger.info("signup ok user_id=%s", user.id)  # never log email/password
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
@limiter.limit(AUTH_RATE_LIMIT)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    user = _find_user_by_email(db, body.email)
    has_password = bool(user and user.password_hash)

    # Always run one argon2 verification so timing doesn't reveal if the email exists.
    password_ok = verify_password(body.password, user.password_hash if has_password else _DUMMY_HASH)

    if not (user and has_password and password_ok):
        raise _unauthorized(GENERIC_LOGIN_ERROR)

    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)
