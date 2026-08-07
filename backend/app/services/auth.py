from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, decode_token, token_fingerprint
from app.models.entities import RefreshToken, User, UserProfile

settings = get_settings()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    email_verified: bool
    name: str | None = None


def verify_google_id_token(raw_token: str) -> GoogleIdentity:
    if not settings.google_client_ids:
        raise HTTPException(status_code=503, detail="Google OAuth client IDs are not configured")
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="google-auth dependency is not installed") from exc

    last_error: Exception | None = None
    for audience in settings.google_client_ids:
        try:
            claims = id_token.verify_oauth2_token(raw_token, google_requests.Request(), audience)
            if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
                raise ValueError("Invalid Google issuer")
            if not claims.get("email"):
                raise ValueError("Google token does not include email")
            return GoogleIdentity(
                subject=str(claims["sub"]),
                email=str(claims["email"]).lower(),
                email_verified=bool(claims.get("email_verified", False)),
                name=claims.get("name"),
            )
        except Exception as exc:  # Google library exposes multiple verification exception types.
            last_error = exc
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google ID token") from last_error


def get_or_create_google_user(db: Session, identity: GoogleIdentity, username: str | None = None) -> User:
    if not identity.email_verified:
        raise HTTPException(status_code=401, detail="Google email must be verified")
    user = db.scalar(select(User).where(User.google_subject == identity.subject))
    if user is None:
        user = db.scalar(select(User).where(User.email == identity.email))
    if user is None:
        user = User(email=identity.email, google_subject=identity.subject, username=username)
        user.profile = UserProfile()
        db.add(user)
    else:
        user.google_subject = identity.subject
        if username and not user.username:
            user.username = username
    db.flush()
    return user


def issue_token_pair(db: Session, user: User, *, user_agent: str | None = None, family_id: str | None = None) -> tuple[str, str]:
    token_id = str(uuid4())
    refresh_token = create_refresh_token(user.id, token_id=token_id)
    record = RefreshToken(
        user_id=user.id,
        token_hash=token_fingerprint(refresh_token),
        family_id=family_id or str(uuid4()),
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days),
        user_agent=user_agent,
    )
    db.add(record)
    db.flush()
    return create_access_token(user.id), refresh_token


def rotate_refresh_token(db: Session, raw_token: str, *, user_agent: str | None = None) -> tuple[User, str, str]:
    try:
        claims = decode_token(raw_token, expected_type="refresh")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

    record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_fingerprint(raw_token)))
    now = datetime.now(timezone.utc)
    if record is None or record.revoked_at is not None or _aware(record.expires_at) <= now:
        if record is not None:
            db.query(RefreshToken).filter(RefreshToken.family_id == record.family_id, RefreshToken.revoked_at.is_(None)).update(
                {RefreshToken.revoked_at: now}, synchronize_session=False
            )
        raise HTTPException(status_code=401, detail="Refresh token is expired, revoked, or already used")
    if record.user_id != claims.get("sub"):
        raise HTTPException(status_code=401, detail="Refresh token subject mismatch")

    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not available")

    access_token, replacement = issue_token_pair(db, user, user_agent=user_agent, family_id=record.family_id)
    replacement_record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_fingerprint(replacement)))
    record.revoked_at = now
    record.replaced_by_id = replacement_record.id if replacement_record else None
    return user, access_token, replacement


def revoke_refresh_token(db: Session, raw_token: str) -> None:
    record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_fingerprint(raw_token)))
    if record and record.revoked_at is None:
        record.revoked_at = datetime.now(timezone.utc)
