from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.entities import User, UserProfile
from app.schemas.auth import DevLoginRequest, GoogleLoginRequest, LogoutRequest, RefreshRequest, TokenPair
from app.services.auth import (
    get_or_create_google_user,
    issue_token_pair,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_google_id_token,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
settings = get_settings()


@router.post("/dev-login", response_model=TokenPair)
def dev_login(payload: DevLoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenPair:
    if not settings.allow_dev_login or settings.environment == "production":
        raise HTTPException(status_code=404, detail="Development login is disabled")
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None:
        user = User(email=str(payload.email).lower(), username=payload.username)
        user.profile = UserProfile()
        db.add(user)
        db.flush()
    elif payload.username and not user.username:
        user.username = payload.username
    access_token, refresh_token = issue_token_pair(db, user, user_agent=request.headers.get("user-agent"))
    db.commit()
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/google", response_model=TokenPair)
def google_login(payload: GoogleLoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenPair:
    identity = verify_google_id_token(payload.id_token)
    user = get_or_create_google_user(db, identity, payload.username)
    access_token, refresh_token = issue_token_pair(db, user, user_agent=request.headers.get("user-agent"))
    db.commit()
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenPair)
def refresh_tokens(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> TokenPair:
    _, access_token, refresh_token = rotate_refresh_token(
        db, payload.refresh_token, user_agent=request.headers.get("user-agent")
    )
    db.commit()
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> None:
    revoke_refresh_token(db, payload.refresh_token)
    db.commit()
