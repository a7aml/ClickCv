#auth_service.py
from app.extensions import db, bcrypt
from app.models.user import User


def register_user(name, email, password):
    """
    Registers a new user with a hashed password.
    Returns (user, error)
    """

    # Check if email already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return None, 'Email already registered.'

    # Hash the password
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    # Create new user
    new_user = User(
        name=name,
        email=email,
        password_hash=hashed_password,
        auth_provider='local'
    )

    db.session.add(new_user)
    db.session.commit()

    return new_user, None


def login_user(email, password):
    """
    Verifies email and password.
    Returns (user, error)
    """

    user = User.query.filter_by(email=email).first()

    if not user:
        return None, 'No account found with this email.'

    if not user.password_hash:
        return None, 'This account uses Google login. Please sign in with Google.'

    if not bcrypt.check_password_hash(user.password_hash, password):
        return None, 'Incorrect password.'

    return user, None