"""
models/cover_letter.py

SQLAlchemy model for the cover_letters table.
Stores AI-generated cover letters linked to resumes and job descriptions.
Follows the same pattern as Resume model: db.Model, typed columns, __repr__.
"""

from app.extensions import db
from datetime import datetime


class CoverLetter(db.Model):
    """
    Stores one AI-generated cover letter per row.

    A user can have multiple cover letters (one per generation session).
    Each cover letter is linked to:
    - The user who generated it (required)
    - The resume used as context (required)
    - The job description it was tailored for (optional)
    
    The cover_letter_text column contains the full generated text.
    Company name and position title are stored for reference.
    """

    __tablename__ = "cover_letters"

    id                   = db.Column(db.Integer, primary_key=True)
    user_id              = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    resume_id            = db.Column(db.Integer, db.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    job_description_id   = db.Column(db.Integer, db.ForeignKey("job_descriptions.id", ondelete="SET NULL"), nullable=True)
    
    # Cover letter content
    cover_letter_text    = db.Column(db.Text, nullable=False)
    
    # Optional metadata from form
    company_name         = db.Column(db.String(255), nullable=True)
    position_title       = db.Column(db.String(255), nullable=True)
    
    # Timestamp
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user                 = db.relationship("User", backref="cover_letters", lazy=True)
    resume               = db.relationship("Resume", backref="cover_letters", lazy=True)
    job_description      = db.relationship("JobDescription", backref="cover_letters", lazy=True)

    def to_dict(self):
        """
        Convert cover letter to dictionary for JSON responses.
        
        Returns:
            dict: Cover letter data including related entities
        """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "resume_id": self.resume_id,
            "job_description_id": self.job_description_id,
            "cover_letter_text": self.cover_letter_text,
            "company_name": self.company_name,
            "position_title": self.position_title,
            "created_at": self.created_at.isoformat(),
            "resume_filename": self.resume.file_name if self.resume else None,
            "job_description_title": self.job_description.title if self.job_description else None,
        }

    def __repr__(self):
        company = self.company_name or "Unknown"
        position = self.position_title or "Unknown Position"
        return f"<CoverLetter {company} - {position} user_id={self.user_id}>"