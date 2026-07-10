"""
models/cv_draft.py

Stores a user's in-progress or completed CV builder session.

Design decisions:
    - Separate from generated_cvs — that table is for AI-rebuild output.
    - mode and status use String columns — DB uses Text, validation in routes.

Table: cv_drafts
"""

from app.extensions import db
from datetime import datetime


class CvDraft(db.Model):
    """One CV builder session per row."""

    __tablename__ = "cv_drafts"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )

    mode = db.Column(
        db.String(20), nullable=False, default="template"
    )  # 'template' or 'assisted'

    template_id = db.Column(
        db.Integer, nullable=False, default=1
    )

    job_description_id = db.Column(
        db.Integer, db.ForeignKey("job_descriptions.id"), nullable=True
    )

    status = db.Column(
        db.String(20), nullable=False, default="draft"
    )  # 'draft' or 'completed'

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user            = db.relationship("User", backref="cv_drafts", lazy=True)
    job_description = db.relationship("JobDescription", backref="cv_drafts", lazy=True)
    sections        = db.relationship(
        "CvDraftSection",
        backref="draft",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="CvDraftSection.position"
    )

    def __repr__(self):
        return (
            f"<CvDraft id={self.id} "
            f"user_id={self.user_id} "
            f"mode={self.mode} "
            f"status={self.status}>"
        )