from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import DEMO_ORGANISATION_NAME, settings
from app.db import get_db
from app.models import Organisation, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")
credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    if len(settings.SECRET_KEY) < 32:
        raise RuntimeError("SECRET_KEY must be configured with at least 32 characters.")
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def get_token_payload(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise credentials_exception from exc
    if payload.get("session_type") == "jury_demo" and not settings.JURY_DEMO_ENABLED:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Jury demo sessions are disabled")
    return payload


def get_current_user(
    payload: dict[str, Any] = Depends(get_token_payload),
    db: Session = Depends(get_db),
) -> User:
    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    if payload.get("session_type") == "jury_demo":
        demo_organisation = db.query(Organisation).filter(
            Organisation.id == user.organisation_id,
            Organisation.name == DEMO_ORGANISATION_NAME,
        ).first()
        if (
            demo_organisation is None
            or payload.get("org_id") != str(user.organisation_id)
            or payload.get("role") != user.role
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid jury demo session")
    return user


def get_jury_session_claims(
    payload: dict[str, Any] = Depends(get_token_payload),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    if payload.get("session_type") != "jury_demo":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="A jury demo session is required")
    try:
        UUID(str(payload.get("jury_session_id")))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid jury demo session") from exc
    if (
        payload.get("sub") != str(current_user.id)
        or payload.get("org_id") != str(current_user.organisation_id)
        or payload.get("role") != current_user.role
        or current_user.role not in {"admin", "reviewer", "creator"}
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid jury demo session")
    return payload

def require_role(allowed_roles: list[str]):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{current_user.role}'. Required: {allowed_roles}"
            )
        return current_user
    return role_checker
