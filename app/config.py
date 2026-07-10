import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:ahMed2005%23@localhost:5432/ClickCv'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'

    # ── JWT ───────────────────────────────────────────────────────────────────
    # Access token: short-lived — 15 minutes
    # If stolen, attacker has at most 15 minutes before it expires.
    JWT_ACCESS_TOKEN_EXPIRES  = timedelta(hours=8)
    # Refresh token: long-lived — 30 days
    # Used ONLY to get a new access token via POST /auth/refresh
    # Stored in httpOnly cookie on the client, not in localStorage.
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # Access tokens come from Authorization header (Bearer)
    # Refresh tokens come from httpOnly cookie
    JWT_TOKEN_LOCATION        = ['headers', 'cookies']

    # Cookie name for refresh token
    JWT_REFRESH_COOKIE_NAME   = 'refresh_token'

    # Only send cookie over HTTPS in production
    # Set to True when you deploy to Railway with a real domain
    JWT_COOKIE_SECURE         = False

    # CSRF protection for cookies — enable in production
    JWT_COOKIE_CSRF_PROTECT   = False

    UPLOAD_FOLDER  = "app/static/uploads"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Flask-Mail — Gmail SMTP
    MAIL_SERVER         = 'smtp.gmail.com'
    MAIL_PORT           = 587
    MAIL_USE_TLS        = True
    MAIL_USERNAME       = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD       = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")