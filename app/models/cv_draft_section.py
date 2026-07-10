"""
models/cv_draft_section.py

Stores one CV section per row for a builder session (CvDraft).

Design decisions:
    - section_type uses String — DB uses Text, validation in route layer.
    - content_json holds all fields for that section type as structured JSON.
    - ai_hint_json stores AI suggestions (Mode 2 only), never auto-merged.

CONTENT_SCHEMAS (reference):
    contact:        {"name":"","email":"","phone":"","location":"","linkedin":"","website":""}
    summary:        {"text":""}
    experience:     [{"job_title":"","company":"","start_date":"","end_date":"","current":false,"description":""}]
    education:      [{"degree":"","institution":"","field_of_study":"","start_date":"","end_date":"","gpa":""}]
    skills:         [{"category":"","skills":[]}]
    projects:       [{"title":"","description":"","tech_stack":"","url":""}]
    certifications: [{"name":"","issuer":"","date":"","credential_url":""}]
    languages:      [{"language":"","proficiency":""}]
    awards:         [{"title":"","issuer":"","date":"","description":""}]
    volunteer:      [{"role":"","organization":"","date_range":"","description":""}]
"""

from app.extensions import db
from datetime import datetime


class CvDraftSection(db.Model):
    """One section of a CV builder draft."""

    __tablename__ = "cv_draft_sections"

    id = db.Column(db.Integer, primary_key=True)

    draft_id = db.Column(
        db.Integer, db.ForeignKey("cv_drafts.id"), nullable=False
    )

    section_type = db.Column(
        db.String(30), nullable=False
    )  # e.g. 'contact', 'experience' — validated in route layer

    position = db.Column(
        db.Integer, nullable=False, default=0
    )

    content_json = db.Column(
        db.JSON, nullable=False, default=dict
    )

    ai_hint_json = db.Column(
        db.JSON, nullable=True, default=None
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint(
            "draft_id", "section_type",
            name="uq_draft_section_type"
        ),
    )

    def __repr__(self):
        return (
            f"<CvDraftSection id={self.id} "
            f"draft_id={self.draft_id} "
            f"type={self.section_type} "
            f"pos={self.position}>"
        )