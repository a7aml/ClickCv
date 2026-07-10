"""
services/google_auth_service.py

Fixes applied vs original:
  1. Welcome email sent ONLY on brand new account creation.
  2. Race condition on simultaneous account creation handled.
  3. Soft delete — deleted users are blocked from logging in via Google.
     Case A: deleted user with matching google_id → blocked.
     Case B: deleted user with matching email → do NOT merge, treat as new
             (or block — configurable via BLOCK_DELETED_GOOGLE_MERGE below).
"""

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.user import User
from flask_jwt_extended import create_access_token
from app.services.mail_service import send_welcome_email

# If True: a Google login matching a DELETED account's email is blocked.
# If False: it creates a brand new account with the same email (not recommended
# since email unique constraint will fail). Keep True for safety.
BLOCK_DELETED_GOOGLE_LOGIN = True


def handle_google_user(google_user_info: dict):
    """
    Create a new user or retrieve an existing one from Google OAuth info.

    Soft delete handling:
      - Case A (existing google_id match): if deleted → block login.
      - Case B (email match): if deleted → block login (don't merge
        a Google account into a deleted local account).
      - Case C (new user): create normally.

    Returns:
        (user, access_token, None)  — success
        (None, None, error_string)  — failure
    """
    email     = google_user_info.get('email')
    name      = google_user_info.get('name')
    google_id = google_user_info.get('sub')

    if not email:
        return None, None, 'Google account has no email address.'

    if not google_id:
        return None, None, 'Google account has no user ID.'

    # ── Case A: Existing Google user ─────────────────────────────────────────
    # Search ALL users (including deleted) to detect the deleted case
    user = User.query.filter_by(google_id=google_id).first()

    if user:
        if user.is_deleted:
            # Soft-deleted user — block login, generic message
            return None, None, 'account_not_found'

        access_token = create_access_token(identity=str(user.id))
        return user, access_token, None

    # ── Case B: Existing local user with same email — merge ──────────────────
    # Search ALL users (including deleted) to detect deleted email match
    existing_email_user = User.query.filter_by(email=email).first()

    if existing_email_user:
        if existing_email_user.is_deleted:
            # Soft-deleted account owns this email — block merge
            return None, None, 'account_not_found'

        # Active user — link Google ID to their existing account
        existing_email_user.google_id     = google_id
        existing_email_user.auth_provider = 'google'

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            existing_email_user = User.query.filter_by(
                email=email, deleted_at=None
            ).first()
            if not existing_email_user:
                return None, None, 'account_merge_failed'

        access_token = create_access_token(identity=str(existing_email_user.id))
        return existing_email_user, access_token, None

    # ── Case C: Brand new user ────────────────────────────────────────────────
    new_user = User(
        name          = name,
        email         = email,
        google_id     = google_id,
        auth_provider = 'google',
        password_hash = None,
    )

    db.session.add(new_user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()

        existing = (
            User.query.filter_by(google_id=google_id, deleted_at=None).first()
            or User.query.filter_by(email=email, deleted_at=None).first()
        )

        if existing:
            access_token = create_access_token(identity=str(existing.id))
            return existing, access_token, None

        return None, None, 'account_creation_failed'

    send_welcome_email(new_user)

    access_token = create_access_token(identity=str(new_user.id))
    return new_user, access_token, None