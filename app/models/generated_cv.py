"""
models/generated_cv.py

Stores AI-rebuilt CV results produced by the rebuild feature.

Design decisions:
    - Links to BOTH resume_analyses (analysis_id) and resumes (resume_id)
      for efficient querying from either direction.
    - sections_json stores the full rebuilt CV as a dict keyed by section
      name, consistent with SectionTypeEnum values.
    - All 10 criterion scores are stored so the frontend can show a
      per-criterion improvement breakdown (original vs rebuilt).
    - original_score is denormalised here (copied from ResumeAnalysis)
      so the comparison view never needs a second query.
    - The original Resume row is never modified — this is always a
      separate record.

Table: generated_cvs

Columns:
    id                       integer PK
    user_id                  integer FK → users.id
    resume_id                integer FK → resumes.id
    analysis_id              integer FK → resume_analyses.id  (UNIQUE)
    sections_json            jsonb   — rebuilt CV sections
    original_score           float   — overall score before rebuild
    rebuilt_score            float   — overall score after rebuild
    score_delta              float   — rebuilt_score - original_score
    keyword_score            float   — criterion 1  (rebuilt)
    keyword_placement_score  float   — criterion 2  (rebuilt)
    formatting_score         float   — criterion 3  (rebuilt)
    structure_score          float   — criterion 4  (rebuilt)
    experience_recency_score float   — criterion 5  (rebuilt)
    achievements_score       float   — criterion 6  (rebuilt)
    job_title_score          float   — criterion 7  (rebuilt)
    education_score          float   — criterion 8  (rebuilt)
    resume_length_score      float   — criterion 9  (rebuilt)
    contact_info_score       float   — criterion 10 (rebuilt)
    missing_keywords         jsonb   — remaining gaps after rebuild
    missing_sections         jsonb   — remaining missing sections
    created_at               timestamp
"""

from app.extensions import db
from datetime import datetime


class GeneratedCv(db.Model):
    """AI-rebuilt CV linked to one analysis session."""

    __tablename__ = "generated_cvs"

    # ── Primary key ───────────────────────────────────────────────────────
    id = db.Column(db.Integer, primary_key=True)

    # ── Foreign keys (both directions as agreed) ──────────────────────────
    user_id     = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False
    )
    resume_id   = db.Column(
        db.Integer, db.ForeignKey("resumes.id"), nullable=False
    )
    analysis_id = db.Column(
        db.Integer, db.ForeignKey("resume_analyses.id"),
        nullable=False, unique=True   # one rebuild per analysis session
    )

    # ── Rebuilt CV content ────────────────────────────────────────────────
    sections_json = db.Column(db.JSON, nullable=False)
    # Example shape:
    # {
    #   "summary":        "...",
    #   "experience":     "...",
    #   "education":      "...",
    #   "skills":         "...",
    #   "projects":       "...",
    #   "certifications": "...",
    #   "achievements":   "..."
    # }

    # ── Score comparison ──────────────────────────────────────────────────
    original_score  = db.Column(db.Float, nullable=False)  # before rebuild
    rebuilt_score   = db.Column(db.Float, nullable=True)   # after rebuild
    score_delta     = db.Column(db.Float, nullable=True)   # rebuilt - original

    # ── 10 criterion scores (rebuilt CV) ──────────────────────────────────
    keyword_score            = db.Column(db.Float, nullable=True)
    keyword_placement_score  = db.Column(db.Float, nullable=True)
    formatting_score         = db.Column(db.Float, nullable=True)
    structure_score          = db.Column(db.Float, nullable=True)
    experience_recency_score = db.Column(db.Float, nullable=True)
    achievements_score       = db.Column(db.Float, nullable=True)
    job_title_score          = db.Column(db.Float, nullable=True)
    education_score          = db.Column(db.Float, nullable=True)
    resume_length_score      = db.Column(db.Float, nullable=True)
    contact_info_score       = db.Column(db.Float, nullable=True)

    # ── Remaining gaps after rebuild ──────────────────────────────────────
    missing_keywords = db.Column(db.JSON, nullable=True, default=list)
    missing_sections = db.Column(db.JSON, nullable=True, default=list)

    # ── Timestamp ─────────────────────────────────────────────────────────
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relationships ─────────────────────────────────────────────────────
    user     = db.relationship("User",           backref="generated_cvs", lazy=True)
    resume   = db.relationship("Resume",         backref="generated_cvs", lazy=True)
    analysis = db.relationship("ResumeAnalysis", backref="generated_cv",  uselist=False, lazy=True)

    def __repr__(self):
        return (
            f"<GeneratedCv id={self.id} "
            f"analysis_id={self.analysis_id} "
            f"delta={self.score_delta:+.1f}>"
        )