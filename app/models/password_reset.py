"""
models/password_reset.py

Stores password reset tokens for the "Forgot Password" flow.

Lifecycle:
    1. User requests reset -> a row is created with a random token
       and expires_at = now + 30 minutes.
    2. User clicks the emailed link -> token is looked up, checked
       for expiry and `used`.
    3. On successful reset, `used` is set to True so the link
       cannot be replayed.

Matches the table created by:

    CREATE TABLE password_reset_tokens (
        id          SERIAL PRIMARY KEY,
        user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token       VARCHAR(128) NOT NULL UNIQUE,
        expires_at  TIMESTAMP NOT NULL,
        used        BOOLEAN NOT NULL DEFAULT FALSE,
        created_at  TIMESTAMP NOT NULL DEFAULT NOW()
    );

    CREATE INDEX ix_password_reset_tokens_token   ON password_reset_tokens (token);
    CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);
"""

from app.extensions import db
from datetime import datetime


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token      = db.Column(db.String(128), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used       = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="password_reset_tokens")

    def is_valid(self) -> bool:
        """True if this token has not been used and has not expired."""
        return (not self.used) and (datetime.utcnow() < self.expires_at)

    def __repr__(self):
        return f"<PasswordResetToken user_id={self.user_id} used={self.used}>"