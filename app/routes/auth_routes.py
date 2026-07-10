"""
routes/auth_routes.py

Fixes applied vs original:
  1. Refresh token added — POST /auth/refresh returns new access token
  2. Token blocklist — logout actually invalidates the token
  3. /me returns full user profile (name, email) not just user_id
  4. Welcome email sent on register only, not on every login
  5. Access token 15 min, refresh token 30 days (set in config.py)
  6. is_admin included in auth response for immediate admin redirect
  7. Comprehensive registration validation including password strength:
       - Email format (RFC-compliant regex)
       - Email max length
       - Name: letters/spaces/hyphens/apostrophes only, 2-100 chars
       - Password: min 6, max 72, no spaces, must contain:
           * at least one uppercase letter
           * at least one lowercase letter
           * at least one digit
           * at least one special character
       - Confirm password match
"""

import re

from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
    decode_token,
)

from app.extensions import db
from app.models.user import User
from app.services.auth_service import register_user, login_user
from app.services.mail_service import send_welcome_email

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# ── In-memory token blocklist ─────────────────────────────────────────────────
_token_blocklist: set = set()


def _is_revoked(jwt_payload: dict) -> bool:
    return jwt_payload.get('jti') in _token_blocklist


def _make_auth_response(user, status_code: int, message: str):
    """Build the standard auth response used by register and login."""
    access_token  = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    response = make_response(jsonify({
        'message':      message,
        'access_token': access_token,
        'user': {
            'id':       user.id,
            'name':     user.name,
            'email':    user.email,
            'is_admin': user.is_admin,
        }
    }), status_code)

    response.set_cookie(
        'refresh_token',
        value    = refresh_token,
        httponly = True,
        samesite = 'Lax',
        secure   = False,          # set True in production
        max_age  = 30 * 24 * 3600,
        path     = '/auth/refresh',
    )

    return response


# ── Validation helpers ────────────────────────────────────────────────────────

_EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
)

_NAME_REGEX = re.compile(
    r"^[a-zA-ZÀ-ÖØ-öø-ÿ]([a-zA-ZÀ-ÖØ-öø-ÿ\s'\-]*[a-zA-ZÀ-ÖØ-öø-ÿ])?$"
)

# Password character class patterns
_HAS_UPPERCASE = re.compile(r'[A-Z]')
_HAS_LOWERCASE = re.compile(r'[a-z]')
_HAS_DIGIT     = re.compile(r'\d')
_HAS_SPECIAL   = re.compile(r'[!@#$%^&*()_+\-=\[\]{};\'\":,.<>?/\\|`~]')


def _validate_password_strength(password: str) -> str | None:
    """
    Check password strength. Returns an error string or None if strong enough.

    Requirements:
        - 6 to 72 characters
        - No spaces
        - At least one uppercase letter  (A-Z)
        - At least one lowercase letter  (a-z)
        - At least one digit             (0-9)
        - At least one special character (!@#$ etc.)

    Returns the FIRST failing rule so the user fixes one thing at a time.
    """
    if not password:
        return 'Password is required.'

    if ' ' in password:
        return 'Password cannot contain spaces.'

    if len(password) < 8:
        return 'Password must be at least 8 characters.'

    if len(password) > 72:
        # bcrypt silently truncates at 72 bytes — be explicit
        return 'Password must be 72 characters or fewer.'

    if not _HAS_UPPERCASE.search(password):
        return 'Password must contain at least one uppercase letter (A-Z).'

    if not _HAS_LOWERCASE.search(password):
        return 'Password must contain at least one lowercase letter (a-z).'

    if not _HAS_DIGIT.search(password):
        return 'Password must contain at least one number (0-9).'

    if not _HAS_SPECIAL.search(password):
        return (
            'Password must contain at least one special character '
            '(e.g. ! @ # $ % ^ & *).'
        )

    return None  # strong enough


def _validate_registration(name: str, email: str,
                            password: str, confirm_password: str) -> str | None:
    """
    Validate all registration fields in order.
    Returns the first error string found, or None if everything passes.
    """

    # ── Name ──────────────────────────────────────────────────────────────
    if not name:
        return 'Full name is required.'

    if len(name) < 2:
        return 'Name must be at least 2 characters.'

    if len(name) > 100:
        return 'Name must be 100 characters or fewer.'

    if not _NAME_REGEX.match(name):
        return (
            'Name can only contain letters, spaces, hyphens, and apostrophes. '
            'Numbers and special characters are not allowed.'
        )

    # ── Email ──────────────────────────────────────────────────────────────
    if not email:
        return 'Email address is required.'

    if len(email) > 150:
        return 'Email address must be 150 characters or fewer.'

    if not _EMAIL_REGEX.match(email):
        return 'Please enter a valid email address (e.g. name@example.com).'

    if '..' in email:
        return 'Email address contains consecutive dots which is not allowed.'

    if email.startswith('.') or email.endswith('.'):
        return 'Email address cannot start or end with a dot.'

    # ── Password strength ──────────────────────────────────────────────────
    pwd_error = _validate_password_strength(password)
    if pwd_error:
        return pwd_error

    # ── Confirm password ───────────────────────────────────────────────────
    if not confirm_password:
        return 'Please confirm your password.'

    if password != confirm_password:
        return 'Passwords do not match.'

    return None


# ── REGISTER ──────────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new local account.

    Expected JSON body:
        {
            "name":             "Ahmed Ali",
            "email":            "ahmed@example.com",
            "password":         "Secret@123",
            "confirm_password": "Secret@123"
        }

    Password requirements:
        - 8 to 72 characters
        - No spaces
        - At least one uppercase letter
        - At least one lowercase letter
        - At least one digit
        - At least one special character (! @ # $ % ^ & * etc.)
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body is required.'}), 400

    name             = data.get('name', '').strip()
    email            = data.get('email', '').strip().lower()
    password         = data.get('password', '')
    confirm_password = data.get('confirm_password', password)

    validation_error = _validate_registration(name, email, password, confirm_password)
    if validation_error:
        return jsonify({'error': validation_error}), 422

    user, error = register_user(name, email, password)
    if error:
        return jsonify({'error': error}), 409

    send_welcome_email(user)

    return _make_auth_response(user, 201, 'Account created successfully.')


# ── LOGIN ─────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['POST'])
def login():
    """Local email/password login."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Request body is required.'}), 400

    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400

    if not _EMAIL_REGEX.match(email):
        return jsonify({'error': 'Invalid email or password.'}), 401

    user, error = login_user(email, password)
    if error:
        return jsonify({'error': error}), 401

    return _make_auth_response(user, 200, 'Login successful.')


# ── REFRESH ───────────────────────────────────────────────────────────────────

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Issue a new access token using the refresh token cookie."""
    jwt_payload = get_jwt()

    if _is_revoked(jwt_payload):
        return jsonify({'error': 'Session expired. Please log in again.'}), 401

    user_id      = get_jwt_identity()
    access_token = create_access_token(identity=user_id)

    return jsonify({
        'access_token': access_token,
        'message':      'Token refreshed.',
    }), 200


# ── LOGOUT ────────────────────────────────────────────────────────────────────

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Revoke the current access token and the refresh token cookie."""
    access_jti = get_jwt().get('jti')
    if access_jti:
        _token_blocklist.add(access_jti)

    refresh_cookie = request.cookies.get('refresh_token')
    if refresh_cookie:
        try:
            decoded     = decode_token(refresh_cookie)
            refresh_jti = decoded.get('jti')
            if refresh_jti:
                _token_blocklist.add(refresh_jti)
        except Exception:
            pass

    response = make_response(
        jsonify({'message': 'Logged out successfully.'}), 200
    )
    response.delete_cookie('refresh_token', path='/auth/refresh')
    return response


# ── GET CURRENT USER ──────────────────────────────────────────────────────────

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    """Return the current user's full profile."""
    jwt_payload = get_jwt()

    if _is_revoked(jwt_payload):
        return jsonify({'error': 'Token revoked. Please log in again.'}), 401

    user_id = get_jwt_identity()
    user    = User.get_active(int(user_id))

    if not user:
        return jsonify({'error': 'User not found.'}), 404

    return jsonify({
        'user_id':       user.id,
        'name':          user.name,
        'email':         user.email,
        'auth_provider': user.auth_provider,
        'is_admin':      user.is_admin,
    }), 200