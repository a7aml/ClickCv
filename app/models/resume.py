"""
models/resume.py

SQLAlchemy model for the resumes table.
Stores the uploaded file reference and extracted raw text.
Mirrors the User model pattern: db.Model, typed columns, __repr__.
"""

from app.extensions import db
from datetime import datetime


class Resume(db.Model):
    """
    Stores one uploaded CV file per row.

    A user can have multiple resumes (one per upload session).
    The raw_text and parsed_data columns are populated by
    extraction_service.py after the file passes validation.
    """

    __tablename__ = "resumes"

    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    file_name    = db.Column(db.String(255), nullable=False)
    file_path    = db.Column(db.Text, nullable=False)
    raw_text     = db.Column(db.Text, nullable=True)       # Full extracted text
    parsed_data  = db.Column(db.JSON, nullable=True)       # Sections as JSON
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    analyses     = db.relationship("ResumeAnalysis", backref="resume", lazy=True)
    sections     = db.relationship("ResumeSection",  backref="resume", lazy=True)

    def __repr__(self):
        return f"<Resume {self.file_name} user_id={self.user_id}>"