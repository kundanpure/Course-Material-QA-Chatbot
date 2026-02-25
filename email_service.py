"""
Email Service — Send verification OTP emails via Gmail SMTP.
Uses aiosmtplib for async sending.
"""
import os
import random
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def generate_otp() -> str:
    """Generate a 6-digit OTP code."""
    return str(random.randint(100000, 999999))


async def send_verification_email(to_email: str, otp_code: str, full_name: str = "") -> bool:
    """
    Send a verification email with OTP code.
    Returns True if sent successfully, False otherwise.
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("[EMAIL] SMTP credentials not configured — skipping email send")
        return False

    greeting = f"Hi {full_name}," if full_name else "Hi there,"

    html_body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #6366f1, #8b5cf6); padding: 32px; text-align: center;">
            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700;">StudyAI</h1>
            <p style="color: rgba(255,255,255,0.85); margin: 8px 0 0; font-size: 14px;">Your Learning Companion</p>
        </div>

        <!-- Body -->
        <div style="padding: 32px;">
            <p style="color: #374151; font-size: 16px; margin: 0 0 16px;">{greeting}</p>
            <p style="color: #374151; font-size: 15px; margin: 0 0 24px;">
                Thanks for signing up! Use this code to verify your email:
            </p>

            <!-- OTP Code -->
            <div style="background: linear-gradient(135deg, #f0f0ff, #f5f3ff); border: 2px dashed #8b5cf6; border-radius: 12px; padding: 24px; text-align: center; margin: 0 0 24px;">
                <p style="color: #6b7280; font-size: 12px; text-transform: uppercase; letter-spacing: 2px; margin: 0 0 8px;">Verification Code</p>
                <p style="color: #4f46e5; font-size: 36px; font-weight: 800; letter-spacing: 8px; margin: 0;">{otp_code}</p>
            </div>

            <p style="color: #6b7280; font-size: 13px; margin: 0 0 8px;">
                ⏱️ This code expires in <strong>10 minutes</strong>.
            </p>
            <p style="color: #6b7280; font-size: 13px; margin: 0;">
                If you didn't create an account, you can safely ignore this email.
            </p>
        </div>

        <!-- Footer -->
        <div style="background: #f9fafb; padding: 16px 32px; text-align: center; border-top: 1px solid #e5e7eb;">
            <p style="color: #9ca3af; font-size: 12px; margin: 0;">
                &copy; 2026 StudyAI — Built with ❤️ for students
            </p>
        </div>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔑 StudyAI — Your verification code is {otp_code}"
    msg["From"] = f"StudyAI <{SMTP_EMAIL}>"
    msg["To"] = to_email

    # Plain text fallback
    plain_text = f"{greeting}\n\nYour StudyAI verification code is: {otp_code}\n\nThis code expires in 10 minutes.\n\nIf you didn't sign up, ignore this email."
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            start_tls=True,
            username=SMTP_EMAIL,
            password=SMTP_PASSWORD,
        )
        print(f"[EMAIL] [OK] Verification email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL] [FAIL] Failed to send email to {to_email}: {e}")
        return False


async def send_password_reset_email(to_email: str, otp_code: str, full_name: str = "") -> bool:
    """Send a password reset OTP email."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("[EMAIL] SMTP credentials not configured")
        return False

    greeting = f"Hi {full_name}," if full_name else "Hi there,"

    html_body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 480px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">
        <div style="background: linear-gradient(135deg, #ef4444, #f97316); padding: 32px; text-align: center;">
            <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700;">StudyAI</h1>
            <p style="color: rgba(255,255,255,0.85); margin: 8px 0 0; font-size: 14px;">Password Reset</p>
        </div>
        <div style="padding: 32px;">
            <p style="color: #374151; font-size: 16px; margin: 0 0 16px;">{greeting}</p>
            <p style="color: #374151; font-size: 15px; margin: 0 0 24px;">
                We received a request to reset your password. Use this code:
            </p>
            <div style="background: linear-gradient(135deg, #fff5f5, #fef2f2); border: 2px dashed #ef4444; border-radius: 12px; padding: 24px; text-align: center; margin: 0 0 24px;">
                <p style="color: #6b7280; font-size: 12px; text-transform: uppercase; letter-spacing: 2px; margin: 0 0 8px;">Reset Code</p>
                <p style="color: #dc2626; font-size: 36px; font-weight: 800; letter-spacing: 8px; margin: 0;">{otp_code}</p>
            </div>
            <p style="color: #6b7280; font-size: 13px; margin: 0 0 8px;">
                This code expires in <strong>10 minutes</strong>.
            </p>
            <p style="color: #6b7280; font-size: 13px; margin: 0;">
                If you didn't request this, you can safely ignore this email. Your password won't change.
            </p>
        </div>
        <div style="background: #f9fafb; padding: 16px 32px; text-align: center; border-top: 1px solid #e5e7eb;">
            <p style="color: #9ca3af; font-size: 12px; margin: 0;">StudyAI &copy; 2026</p>
        </div>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"StudyAI -- Password Reset Code: {otp_code}"
    msg["From"] = f"StudyAI <{SMTP_EMAIL}>"
    msg["To"] = to_email

    plain_text = f"{greeting}\n\nYour password reset code is: {otp_code}\n\nThis code expires in 10 minutes.\nIf you didn't request this, ignore this email."
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            start_tls=True,
            username=SMTP_EMAIL,
            password=SMTP_PASSWORD,
        )
        print(f"[EMAIL] [OK] Password reset email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL] [FAIL] Failed to send reset email to {to_email}: {e}")
        return False
