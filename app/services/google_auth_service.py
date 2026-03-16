from app.extensions import db
from app.models.user import User
from flask_jwt_extended import create_access_token


def handle_google_user(google_user_info):
    """
    Receives user info from Google.
    Creates new user or logs in existing user.
    Returns (user, access_token, error)
    """

    email     = google_user_info.get('email')
    name      = google_user_info.get('name')
    google_id = google_user_info.get('sub')  # Google's unique user ID

    if not email:
        return None, None, 'Google account has no email address.'

    # Check if user already exists with this Google ID
    user = User.query.filter_by(google_id=google_id).first()

    if user:
        # Existing Google user — just log them in
        access_token = create_access_token(identity=str(user.id))
        return user, access_token, None

    # Check if user registered with email/password before
    existing_email_user = User.query.filter_by(email=email).first()

    if existing_email_user:
        # Merge — link Google ID to existing account
        existing_email_user.google_id    = google_id
        existing_email_user.auth_provider = 'google'
        db.session.commit()
        access_token = create_access_token(identity=str(existing_email_user.id))
        return existing_email_user, access_token, None

    # Brand new user — create account automatically
    new_user = User(
        name          = name,
        email         = email,
        google_id     = google_id,
        auth_provider = 'google',
        password_hash = None   # No password for Google users
    )

    db.session.add(new_user)
    db.session.commit()

    access_token = create_access_token(identity=str(new_user.id))
    return new_user, access_token, None