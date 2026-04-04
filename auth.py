"""
Auth Module — JWT-based authentication for production_agentic.py
Uses passlib+bcrypt for password hashing, python-jose for JWT.
Includes Google OAuth token verification.
"""
import os
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Request, HTTPException
from dotenv import load_dotenv

load_dotenv()

# ─── Config ────────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-random-string-change-this-12345")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

# ─── Password Hashing ─────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ─── JWT Token ─────────────────────────────────────────────────────────────────

def create_jwt(user_id: int, email: str) -> str:
    """Create a JWT access token with user_id and email."""
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_jwt(token: str) -> Dict:
    """Decode and validate a JWT token. Returns payload dict."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        email = payload.get("email")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"user_id": int(user_id), "email": email}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ─── FastAPI Dependencies ──────────────────────────────────────────────────────

async def get_current_user(request: Request) -> Dict:
    """
    FastAPI dependency: extracts Bearer token from Authorization header,
    decodes it, and returns {user_id, email}.
    Raises 401 if missing or invalid.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header.split(" ", 1)[1]
    return decode_jwt(token)


async def get_optional_user(request: Request) -> Optional[Dict]:
    """
    FastAPI dependency: same as get_current_user but returns None
    instead of raising if no token is provided.
    For backward-compatible endpoints that work with or without auth.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ", 1)[1]
    try:
        return decode_jwt(token)
    except HTTPException:
        return None


# ─── Google OAuth Token Verification ──────────────────────────────────────────

async def verify_google_token(id_token: str) -> Optional[Dict]:
    """
    Verify a Google ID token via Google's tokeninfo endpoint.
    Returns user info dict {sub, email, name, picture} or None on failure.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
            )
            if resp.status_code != 200:
                print(f"[GOOGLE AUTH] Token verification failed: {resp.status_code}")
                return None

            data = resp.json()

            # Verify the token is for our app
            if data.get("aud") != GOOGLE_CLIENT_ID:
                print(f"[GOOGLE AUTH] Token audience mismatch")
                return None

            return {
                "sub": data.get("sub"),          # Google user ID
                "email": data.get("email"),
                "name": data.get("name", ""),
                "picture": data.get("picture", ""),
                "email_verified": data.get("email_verified", "false") == "true",
            }
    except Exception as e:
        print(f"[GOOGLE AUTH] Error verifying token: {e}")
        return None
