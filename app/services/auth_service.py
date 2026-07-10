"""
services/auth_service.py

Fixes applied vs original:
  1. Timing attack fix — bcrypt always runs even when user not found.
  2. Generic error messages — wrong email and wrong password look identical.
  3. Soft delete — login blocked for deleted_at users.
  4. ADDED — name sanitisation before saving:
       - Collapses multiple internal spaces to one
       - Title-cases the name for consistent display
"""

import re
from app.extensions import db, bcrypt
from app.models.user import User

_DUMMY_HASH = bcrypt.generate_password_hash('dummy_password_for_timing').decode('utf-8')


def _sanitise_name(name: str) -> str:
    """
    Clean up a name before saving:
      - Collapse multiple internal spaces to a single space
        e.g. "Ahmed  Ali" -> "Ahmed Ali"
      - Title-case for consistent display
        e.g. "ahmed ali" -> "Ahmed Ali"
    """
    name = re.sub(r'\s+', ' ', name).strip()
    return name.title()


def register_user(name: str, email: str, password: str):
    """
    Register a new local user with a hashed password.

    All field format validation is done in auth_routes._validate_registration()
    before this function is called. This function only checks:
      - Email uniqueness (including soft-deleted accounts)

    Returns:
        (user, None)    -- success
        (None, error)   -- failure
    """
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return None, 'This email address is already registered. Please log in or use a different email.'

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    new_user = User(
        name          = _sanitise_name(name),
        email         = email,
        password_hash = hashed_password,
        auth_provider = 'local',
    )

    db.session.add(new_user)
    db.session.commit()

    return new_user, None


def login_user(email: str, password: str):
    """
    Verify email and password for local login.

    Soft-deleted users get the same generic error as wrong credentials.

    Returns:
        (user, None)    -- success
        (None, error)   -- failure
    """
    user = User.query.filter_by(email=email, deleted_at=None).first()

    if not user:
        bcrypt.check_password_hash(_DUMMY_HASH, password)
        return None, 'Invalid email or password.'

    if not user.password_hash:
        bcrypt.check_password_hash(_DUMMY_HASH, password)
        return None, 'This account uses Google login. Please sign in with Google.'

    if not bcrypt.check_password_hash(user.password_hash, password):
        return None, 'Invalid email or password.'

    return user, None