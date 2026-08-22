"""
Authentication helpers: password hashing (bcrypt) + JWT tokens.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

import database as db

# ─── Config ───────────────────────────────────────────
SECRET_KEY  = "cim-generator-jwt-secret-change-in-production-2024"
ALGORITHM   = "HS256"
TOKEN_TTL_HOURS = 72          # 3 days

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer = HTTPBearer(auto_error=False)


# ─── Password ─────────────────────────────────────────

def hash_password(plain: str) -> str:
    return _pwd.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


# ─── JWT ──────────────────────────────────────────────

def create_token(user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    return jwt.encode(
        {"sub": user_id, "email": email, "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM
    )

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── FastAPI dependency ────────────────────────────────

def get_current_user(request: Request, creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    # Support ?token= query param for download links (browser <a> tags can't set headers)
    raw_token = None
    if creds:
        raw_token = creds.credentials
    elif request.query_params.get("token"):
        raw_token = request.query_params["token"]

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(raw_token)
    user_id = payload.get("sub")
    user = db.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists.")
    return user


# ─── Registration & Login logic ───────────────────────

def register_user(email: str, name: str, password: str) -> dict:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if db.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    uid = str(uuid.uuid4())
    user = db.create_user(uid, email, name, hash_password(password))
    token = create_token(uid, email)
    return {"user": user, "token": token}


def login_user(email: str, password: str) -> dict:
    user = db.get_user_by_email(email)
    if not user or not verify_password(password, user["password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    token = create_token(user["id"], user["email"])
    return {"user": {"id": user["id"], "email": user["email"], "name": user["name"]}, "token": token}


# ─── Session ownership guard ──────────────────────────

def assert_session_owner(session_id: str, user: dict):
    """Raises 403 if the current user does not own this session."""
    owner_id = db.get_session_owner(session_id)
    if owner_id is None:
        # Session not bound yet (legacy / in-memory only) — allow but don't leak
        return
    if owner_id != user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This session belongs to another user."
        )
