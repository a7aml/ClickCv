import os
import requests
from flask import Blueprint, redirect, request, session
from app.services.google_auth_service import handle_google_user

google_bp = Blueprint('google_auth', __name__, url_prefix='/auth/google')


def init_google_oauth(app):
    """Called from create_app() — nothing to initialize for requests-based approach."""
    pass


# Google OAuth URLs
GOOGLE_AUTH_URL     = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL    = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'


# ─────────────────────────────────────────
# STEP 1: Redirect user to Google login
# ─────────────────────────────────────────
@google_bp.route('/login')
def google_login():
    client_id    = os.environ.get('GOOGLE_CLIENT_ID')
    redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI')

    # Build Google authorization URL manually
    params = (
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=openid%20email%20profile"
        f"&access_type=offline"
    )

    return redirect(GOOGLE_AUTH_URL + params)


# ─────────────────────────────────────────
# STEP 2: Google redirects back here
# ─────────────────────────────────────────
@google_bp.route('/callback')
def google_callback():
    try:
        code = request.args.get('code')

        if not code:
            return redirect('/signin?error=google_failed')

        client_id     = os.environ.get('GOOGLE_CLIENT_ID')
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        redirect_uri  = os.environ.get('GOOGLE_REDIRECT_URI')

        # Exchange code for access token
        token_response = requests.post(GOOGLE_TOKEN_URL, data={
            'code':          code,
            'client_id':     client_id,
            'client_secret': client_secret,
            'redirect_uri':  redirect_uri,
            'grant_type':    'authorization_code',
        })

        token_data   = token_response.json()
        access_token = token_data.get('access_token')

        if not access_token:
            print(f'Token error: {token_data}')
            return redirect('/signin?error=google_failed')

        # Get user info from Google
        userinfo_response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={'Authorization': f'Bearer {access_token}'}
        )

        google_user_info = userinfo_response.json()

        if not google_user_info.get('email'):
            return redirect('/signin?error=google_failed')

        # Handle user creation or login in our DB
        user, jwt_token, error = handle_google_user(google_user_info)

        if error:
            return redirect(f'/signin?error={error}')

        # Redirect to dashboard with JWT token in URL
        # auth.js picks it up and saves to localStorage
        return redirect(f'/dashboard?token={jwt_token}')

    except Exception as e:
        print(f'Google OAuth error: {e}')
        return redirect('/signin?error=google_failed')