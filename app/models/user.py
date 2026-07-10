from app.extensions import db
from datetime import datetime


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=True)
    auth_provider = db.Column(db.String(20), default='local')
    google_id = db.Column(db.String(255), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    # Soft delete — set when user is deleted, None means active
    deleted_at = db.Column(db.DateTime, nullable=True, default=None)

    # ── Soft delete helpers ──────────────────────────────────

    @property
    def is_deleted(self):
        """Returns True if this user has been soft deleted."""
        return self.deleted_at is not None

    def soft_delete(self):
        """Mark user as deleted without removing from DB."""
        self.deleted_at = datetime.utcnow()
        db.session.commit()

    def restore(self):
        """Restore a soft-deleted user."""
        self.deleted_at = None
        db.session.commit()

    @staticmethod
    def get_active(user_id):
        """Fetch a user only if they are not deleted."""
        return User.query.filter_by(id=user_id, deleted_at=None).first()

    def __repr__(self):
        status = 'deleted' if self.is_deleted else 'active'
        return f'<User {self.email} ({status})>'