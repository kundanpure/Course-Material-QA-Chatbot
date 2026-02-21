"""
Auth Routes — Register, Login, Profile
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from typing import Optional

import db_postgres as db
from auth import hash_password, verify_password, create_jwt, get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


# ─── Request / Response Models ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


class UserProfile(BaseModel):
    id: int
    email: str
    full_name: str
    provider: str
    avatar_url: Optional[str] = None
    created_at: str


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest):
    """Create a new user account."""
    # Validate
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if not req.email or "@" not in req.email:
        raise HTTPException(400, "Invalid email address")
    if not req.full_name.strip():
        raise HTTPException(400, "Full name is required")

    # Check if email already exists
    existing = await db.get_user_by_email(req.email.lower().strip())
    if existing:
        raise HTTPException(409, "Email already registered")

    # Create user
    hashed = hash_password(req.password)
    user = await db.create_user(
        email=req.email.lower().strip(),
        full_name=req.full_name.strip(),
        hashed_pw=hashed,
    )
    if not user:
        raise HTTPException(500, "Failed to create user")

    # Generate token
    token = create_jwt(user["id"], user["email"])
    await db.update_last_login(user["id"])

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "provider": user["provider"],
            "avatar_url": user.get("avatar_url"),
            "created_at": str(user["created_at"]),
        },
    }


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """Login with email and password."""
    user = await db.get_user_by_email(req.email.lower().strip())
    if not user:
        raise HTTPException(401, "Invalid email or password")

    if not verify_password(req.password, user["hashed_pw"]):
        raise HTTPException(401, "Invalid email or password")

    # Generate token
    token = create_jwt(user["id"], user["email"])
    await db.update_last_login(user["id"])

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "provider": user["provider"],
            "avatar_url": user.get("avatar_url"),
            "created_at": str(user["created_at"]),
        },
    }


@router.get("/me")
async def get_profile(request: Request):
    """Get current user profile (requires auth)."""
    current = await get_current_user(request)
    user = await db.get_user_by_id(current["user_id"])
    if not user:
        raise HTTPException(404, "User not found")

    return {
        "id": user["id"],
        "email": user["email"],
        "full_name": user["full_name"],
        "provider": user["provider"],
        "avatar_url": user.get("avatar_url"),
        "created_at": str(user["created_at"]),
    }
