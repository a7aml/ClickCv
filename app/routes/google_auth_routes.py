"""
routes/google_auth_routes.py

Fixes applied vs original:
  1. CSRF state parameter added — random token stored in session,
     verified when Google calls back. Prevents OAuth hijacking.
  2. JWT token no longer passed in URL — one-time code pattern used instead.
     Frontend exchanges the code for tokens via POST /auth/google/token.
  3. session is now actually used (was imported but unused before).
  4. Refresh token added alongside access token on Google login.
  5. Error messages are specific enough to debug but safe to show users.

Flow:
  GET  /auth/google/login    → redirect to Google with state parameter
  GET  /auth/google/callback → verify state, exchange code, set one-time code
  POST /auth/google/token    → frontend exchanges one-time code for JWT tokens
"""

import os
import secrets
import requests

from flask import Blueprint, redirect, request, session, jsonify, make_response
from flask_jwt_extended import create_access_token, create_refresh_token

from app.services.google_auth_service import handle_google_user

google_bp = Blueprint('google_auth', __name__, url_prefix='/auth/google')


def init_google_oauth(app):
    """Called from create_app() — ensures SECRET_KEY is set for session use."""
    if not app.secret_key:
        raise RuntimeError(
            "SECRET_KEY must be set in config for Google OAuth session support."
        )


# Google OAuth URLs
GOOGLE_AUTH_URL     = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL    = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'

# In-memory one-time code store: {code: user_id}
# Each code is valid for one exchange only, then deleted.
# In production replace with Redis with a 5-minute TTL.
_one_time_codes: dict = {}


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Redirect user to Google login
# ─────────────────────────────────────────────────────────────────────────────

@google_bp.route('/login')
def google_login():
    """
    Generate a CSRF state token, store it in the session,
    then redirect the user to Google's OAuth consent screen.

    The state parameter prevents CSRF attacks on the OAuth flow.
    Google echoes it back in the callback — we verify it matches.
    """
    client_id    = os.environ.get('GOOGLE_CLIENT_ID')
    redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI')

    if not client_id or not redirect_uri:
        return redirect('/signin?error=oauth_config_missing')

    # Generate a random state token for CSRF protection
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state

    params = (
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=openid%20email%20profile"
        f"&access_type=offline"
        f"&state={state}"
        f"&prompt=consent"
    )

    return redirect(GOOGLE_AUTH_URL + params)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Google redirects back here
# ─────────────────────────────────────────────────────────────────────────────

@google_bp.route('/callback')
def google_callback():
    """
    Handle Google's OAuth callback.

    Fixes:
      - Verify CSRF state parameter before doing anything.
      - Do NOT put the JWT in the URL (browser history / log exposure).
      - Instead generate a short-lived one-time code and redirect to
        a frontend page that immediately POSTs the code to /auth/google/token.
    """
    try:
        # ── 1. Verify CSRF state ──────────────────────────────────────────────
        returned_state  = request.args.get('state', '')
        expected_state  = session.pop('oauth_state', None)

        if not expected_state or returned_state != expected_state:
            # State mismatch — possible CSRF attack
            return redirect('/signin?error=oauth_state_invalid')

        # ── 2. Check for error from Google ────────────────────────────────────
        error = request.args.get('error')
        if error:
            return redirect(f'/signin?error=google_{error}')

        code = request.args.get('code')
        if not code:
            return redirect('/signin?error=google_no_code')

        # ── 3. Exchange code for Google access token ──────────────────────────
        client_id     = os.environ.get('GOOGLE_CLIENT_ID')
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        redirect_uri  = os.environ.get('GOOGLE_REDIRECT_URI')

        token_response = requests.post(GOOGLE_TOKEN_URL, data={
            'code':          code,
            'client_id':     client_id,
            'client_secret': client_secret,
            'redirect_uri':  redirect_uri,
            'grant_type':    'authorization_code',
        }, timeout=10)

        token_data          = token_response.json()
        google_access_token = token_data.get('access_token')

        if not google_access_token:
            return redirect('/signin?error=google_token_failed')

        # ── 4. Fetch user info from Google ────────────────────────────────────
        userinfo_response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f'Bearer {google_access_token}'},
            timeout=10,
        )

        google_user_info = userinfo_response.json()

        if not google_user_info.get('email'):
            return redirect('/signin?error=google_no_email')

        # ── 5. Create or find the user in our DB ──────────────────────────────
        user, _, error = handle_google_user(google_user_info)

        if error:
            return redirect(f'/signin?error={error}')

        # ── 6. Generate one-time code instead of putting JWT in URL ───────────
        # The code is a random token that the frontend exchanges for real JWTs
        # via POST /auth/google/token within 5 minutes.
        # This means the JWT never appears in the browser URL, history, or logs.
        one_time_code = secrets.token_urlsafe(32)
        _one_time_codes[one_time_code] = str(user.id)

        # Redirect to a dedicated exchange page — NOT the dashboard
        # The frontend page immediately POSTs the code and then navigates
        return redirect(f'/auth/google/exchange?code={one_time_code}')

    except requests.Timeout:
        return redirect('/signin?error=google_timeout')
    except Exception as e:
        print(f'Google OAuth error: {e}')
        return redirect('/signin?error=google_failed')


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Frontend exchanges one-time code for JWT tokens
# ─────────────────────────────────────────────────────────────────────────────

@google_bp.route('/token', methods=['POST'])
def exchange_token():
    """
    Exchange a one-time code for JWT access + refresh tokens.

    The frontend calls this immediately after the callback redirect.
    The code is deleted after one use — replay attacks are impossible.

    Body: { "code": "<one_time_code>" }

    Returns:
      - access_token in JSON body
      - refresh_token in httpOnly cookie (same pattern as local auth)
    """
    data = request.get_json()
    if not data or not data.get('code'):
        return jsonify({'error': 'Code is required.'}), 400

    code    = data['code']
    user_id = _one_time_codes.pop(code, None)  # pop = one-time use

    if not user_id:
        return jsonify({
            'error': 'Invalid or expired code. Please sign in again.'
        }), 401

    from app.models.user import User
    user = User.query.get(int(user_id))

    if not user:
        return jsonify({'error': 'User not found.'}), 404

    access_token  = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    response = make_response(jsonify({
        'message':      'Google login successful.',
        'access_token': access_token,
        'user': {
            'id':    user.id,
            'name':  user.name,
            'email': user.email,
        }
    }), 200)

    # Set refresh token as httpOnly cookie — same as local auth
    response.set_cookie(
        'refresh_token',
        value    = refresh_token,
        httponly = True,
        samesite = 'Lax',
        secure   = False,           # set True in production
        max_age  = 30 * 24 * 3600,  # 30 days
        path     = '/auth/refresh',
    )

    return response