"""
Auth Routes — Register (with OTP), Login, Verify Email, Google OAuth, Profile
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

import db_postgres as db
from auth import hash_password, verify_password, create_jwt, get_current_user, verify_google_token
from email_service import generate_otp, send_verification_email, send_password_reset_email

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


# ─── Request / Response Models ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyEmailRequest(BaseModel):
    email: str
    code: str


class ResendCodeRequest(BaseModel):
    email: str


class GoogleLoginRequest(BaseModel):
    credential: str  # Google ID token from frontend


class AuthResponse(BaseModel):
    token: str
    user: dict


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register")
async def register(req: RegisterRequest):
    """Create a new user account and send verification OTP."""
    # Validate
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if not req.email or "@" not in req.email:
        raise HTTPException(400, "Invalid email address")
    if not req.full_name.strip():
        raise HTTPException(400, "Full name is required")

    email = req.email.lower().strip()

    # Check if email already exists
    existing = await db.get_user_by_email(email)
    if existing:
        # If user exists but not verified, resend code
        if not existing.get("is_verified", False):
            otp = generate_otp()
            expires = datetime.utcnow() + timedelta(minutes=10)
            await db.set_verification_code(email, otp, expires)
            await send_verification_email(email, otp, existing.get("full_name", ""))
            return {
                "requires_verification": True,
                "email": email,
                "message": "Verification code resent to your email",
            }
        raise HTTPException(409, "Email already registered")

    # Create user
    hashed = hash_password(req.password)
    user = await db.create_user(
        email=email,
        full_name=req.full_name.strip(),
        hashed_pw=hashed,
    )
    if not user:
        raise HTTPException(500, "Failed to create user")

    # Generate OTP and send email
    otp = generate_otp()
    expires = datetime.utcnow() + timedelta(minutes=10)
    await db.set_verification_code(email, otp, expires)
    email_sent = await send_verification_email(email, otp, req.full_name.strip())

    return {
        "requires_verification": True,
        "email": email,
        "message": "Verification code sent to your email" if email_sent else "Account created — check your email for verification code",
    }


@router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest):
    """Verify email with OTP code and return JWT token."""
    email = req.email.lower().strip()
    code = req.code.strip()

    if not code or len(code) != 6:
        raise HTTPException(400, "Invalid verification code")

    verified = await db.verify_user_email(email, code)
    if not verified:
        raise HTTPException(400, "Invalid or expired verification code")

    # Get user and generate token
    user = await db.get_user_by_email(email)
    if not user:
        raise HTTPException(404, "User not found")

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


@router.post("/resend-code")
async def resend_code(req: ResendCodeRequest):
    """Resend verification OTP to email."""
    email = req.email.lower().strip()
    user = await db.get_user_by_email(email)

    if not user:
        raise HTTPException(404, "No account found with this email")

    if user.get("is_verified", False):
        raise HTTPException(400, "Email already verified")

    otp = generate_otp()
    expires = datetime.utcnow() + timedelta(minutes=10)
    await db.set_verification_code(email, otp, expires)
    await send_verification_email(email, otp, user.get("full_name", ""))

    return {"message": "Verification code resent", "email": email}


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """Login with email and password."""
    user = await db.get_user_by_email(req.email.lower().strip())
    if not user:
        raise HTTPException(401, "Invalid email or password")

    # Check if user registered via Google (no password)
    if user.get("provider") == "google" and not user.get("hashed_pw"):
        raise HTTPException(400, "This account uses Google Sign-In. Please login with Google.")

    if not verify_password(req.password, user["hashed_pw"]):
        raise HTTPException(401, "Invalid email or password")

    # Check email verification
    if not user.get("is_verified", False):
        # Resend OTP automatically
        otp = generate_otp()
        expires = datetime.utcnow() + timedelta(minutes=10)
        await db.set_verification_code(user["email"], otp, expires)
        await send_verification_email(user["email"], otp, user.get("full_name", ""))
        raise HTTPException(403, "Email not verified. A new verification code has been sent.")

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


@router.post("/google")
async def google_login(req: GoogleLoginRequest):
    """Authenticate with Google. Creates account if first time."""
    google_user = await verify_google_token(req.credential)
    if not google_user:
        raise HTTPException(401, "Invalid Google token")

    # Get or create user
    user = await db.get_or_create_google_user(
        google_id=google_user["sub"],
        email=google_user["email"],
        full_name=google_user["name"],
        avatar_url=google_user.get("picture"),
    )
    if not user:
        raise HTTPException(500, "Failed to process Google login")

    token = create_jwt(user["id"], user["email"])
    await db.update_last_login(user["id"])

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "provider": user.get("provider", "google"),
            "avatar_url": user.get("avatar_url"),
            "created_at": str(user["created_at"]),
        },
    }


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """Send a password reset OTP to the user's email."""
    email = req.email.lower().strip()
    user = await db.get_user_by_email(email)

    if not user:
        raise HTTPException(404, "No account found with this email address")

    if user.get("provider") == "google" and not user.get("hashed_pw"):
        raise HTTPException(400, "This account uses Google Sign-In. Please login with Google instead.")

    otp = generate_otp()
    expires = datetime.utcnow() + timedelta(minutes=10)
    await db.set_verification_code(email, otp, expires)
    await send_password_reset_email(email, otp, user.get("full_name", ""))

    return {"message": "Reset code sent to your email", "email": email}


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """Reset password using OTP code."""
    email = req.email.lower().strip()
    code = req.code.strip()

    if len(req.new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    if not code or len(code) != 6:
        raise HTTPException(400, "Invalid reset code")

    # Verify the OTP
    verified = await db.verify_user_email(email, code)
    if not verified:
        raise HTTPException(400, "Invalid or expired reset code")

    # Update the password
    user = await db.get_user_by_email(email)
    if not user:
        raise HTTPException(404, "User not found")

    hashed = hash_password(req.new_password)
    # Update password in DB
    if db.db_pool:
        async with db.db_pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET hashed_pw = $1, is_verified = TRUE WHERE email = $2",
                hashed, email,
            )

    return {"message": "Password reset successful. You can now login with your new password."}


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
