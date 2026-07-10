"""
services/password_reset_service.py

Business logic for the "Forgot Password" flow.

Functions:
    request_password_reset(email)
        - Looks up the user (silently, no enumeration).
        - If a LOCAL account exists, creates a reset token (30 min)
          and sends a reset-link email.
        - If a GOOGLE account exists, sends a "use Google sign-in"
          email instead — no token created.
        - If no account exists, does nothing.
        - ALWAYS returns success — caller returns the same generic
          message regardless of which branch ran (anti-enumeration).

    reset_password(token, new_password)
        - Validates the token (exists, not used, not expired).
        - Hashes and sets the new password.
        - Marks the token as used.
        - Returns (True, None) or (False, error_message).
"""

import secrets
from datetime import datetime, timedelta

from app.extensions import db, bcrypt
from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.services.mail_service import (
    send_password_reset_email,
    send_password_reset_google_notice_email,
)

# How long a reset link stays valid.
RESET_TOKEN_EXPIRY_MINUTES = 30

# Minimum length for a new password — mirrors register_user() validation.
MIN_PASSWORD_LENGTH = 6


def request_password_reset(email: str) -> None:
    """
    Handle a "forgot password" request.

    This function intentionally NEVER reveals whether an account exists.
    The route always returns the same generic message regardless of
    what happens here. Errors are swallowed for the same reason —
    a failure must not leak information via response timing/content
    beyond what send_welcome_email() already risks (and that is
    logged, not raised).

    Behaviour:
        - No user with this email      -> do nothing.
        - Google-only account          -> send a "use Google" notice email,
                                           no token created.
        - Local account (has password) -> create a reset token and
                                           email the reset link.
    """
    email = (email or "").strip().lower()
    if not email:
        return

    user = User.query.filter_by(email=email).first()
    if not user:
        return

    # Google-only account — no local password to reset.
    if not user.password_hash:
        send_password_reset_google_notice_email(user)
        return

    # Local account — generate a fresh token.
    # Invalidate any previous unused tokens for this user so only the
    # most recent link works.
    PasswordResetToken.query.filter_by(user_id=user.id, used=False).update(
        {"used": True}
    )

    token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES),
        used=False,
    )
    db.session.add(reset_token)
    db.session.commit()

    send_password_reset_email(user, token)


def reset_password(token: str, new_password: str) -> tuple:
    """
    Complete a password reset using a token from the emailed link.

    Args:
        token:        the raw token string from the reset link
        new_password: the user's chosen new password (plaintext)

    Returns:
        (True, None)            — success, password updated
        (False, error_message)  — invalid/expired token or bad password
    """
    if not token:
        return False, "Reset token is required."

    if not new_password or len(new_password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters."

    reset_token = PasswordResetToken.query.filter_by(token=token).first()

    # Generic message for any invalid/expired/used/missing token —
    # do not distinguish between "not found", "expired", and "used"
    # so an attacker cannot probe token validity.
    if not reset_token or not reset_token.is_valid():
        return False, "This reset link is invalid or has expired. Please request a new one."

    user = User.query.get(reset_token.user_id)
    if not user:
        return False, "This reset link is invalid or has expired. Please request a new one."

    user.password_hash = bcrypt.generate_password_hash(new_password).decode("utf-8")
    reset_token.used = True

    db.session.commit()

    return True, None