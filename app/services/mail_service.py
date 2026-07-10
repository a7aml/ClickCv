"""
services/mail_service.py

Handles all outgoing emails for ClickCV.
Uses Flask-Mail with Gmail SMTP.

Functions:
    send_welcome_email(user)
        — sent after registration or first Google login

    send_password_reset_email(user, token)
        — sent when a LOCAL account requests a password reset.
          Contains a link: {FRONTEND_URL}/reset-password?token=...

    send_password_reset_google_notice_email(user)
        — sent when a "forgot password" request is made for an
          account that uses Google sign-in (no local password to reset).
"""

import os
from flask import render_template, current_app
from flask_mail import Message
from app.extensions import mail


def send_welcome_email(user) -> None:
    """
    Send a branded welcome email to a newly registered user.

    Args:
        user: User model instance — must have .name and .email attributes

    Returns:
        None — errors are logged but never raised so they
        never block the registration response.
    """
    try:
        msg = Message(
            subject="Welcome to ClickCV 🎯",
            recipients=[user.email],
            html=render_template(
                "emails/welcome.html",
                name=user.name,
            ),
        )
        mail.send(msg)
        current_app.logger.info(f"Welcome email sent to {user.email}")

    except Exception as e:
        # Never let email failure break registration
        current_app.logger.error(
            f"Failed to send welcome email to {user.email}: {e}"
        )


def send_password_reset_email(user, token: str) -> None:
    """
    Send a password reset link to a LOCAL account.

    The link points to the frontend reset-password page with the
    raw token as a query parameter:

        {FRONTEND_URL}/reset-password?token=<token>

    FRONTEND_URL defaults to http://127.0.0.1:5000 for local dev.
    Set FRONTEND_URL in .env for production deployments.

    Args:
        user:  User model instance — must have .name and .email
        token: the raw (unhashed) reset token string

    Returns:
        None — errors are logged but never raised, so a mail
        failure never reveals account existence to the caller.
    """
    try:
        frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5000").rstrip("/")
        reset_link = f"{frontend_url}/reset-password?token={token}"

        msg = Message(
            subject="Reset your ClickCV password",
            recipients=[user.email],
            html=render_template(
                "emails/password_reset.html",
                name=user.name,
                reset_link=reset_link,
            ),
        )
        mail.send(msg)
        current_app.logger.info(f"Password reset email sent to {user.email}")

    except Exception as e:
        current_app.logger.error(
            f"Failed to send password reset email to {user.email}: {e}"
        )


def send_password_reset_google_notice_email(user) -> None:
    """
    Sent when a "forgot password" request is made for an account that
    signs in via Google (user.password_hash is None).

    Informs the user there is no local password to reset and that
    they should use "Sign in with Google" instead.

    Args:
        user: User model instance — must have .name and .email

    Returns:
        None — errors are logged but never raised.
    """
    try:
        msg = Message(
            subject="ClickCV password reset — use Google Sign-In",
            recipients=[user.email],
            html=render_template(
                "emails/password_reset_google_notice.html",
                name=user.name,
            ),
        )
        mail.send(msg)
        current_app.logger.info(f"Google-account reset notice sent to {user.email}")

    except Exception as e:
        current_app.logger.error(
            f"Failed to send Google-account reset notice to {user.email}: {e}"
        )