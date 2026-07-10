"""
models/analysis.py

SQLAlchemy models matching the exact DB schema from pgAdmin.

Tables covered:
    resume_analyses     — one analysis session per row
    ats_results         — 10 criterion scores per analysis
    resume_sections     — one row per detected section per resume
    recommendations     — LLM-generated recommendations per analysis
    job_descriptions    — stored JD text per user
    resume_comparisons  — one comparison session per row
    comparison_resumes  — individual CV scores per comparison

FIX: ResumeSection.section_type now references the enum type by its REAL
     name in the database — "section_type_enum" — via name=... and uses
     create_type=False so SQLAlchemy never tries to (re)create it.

     The DB enum was created as public.section_type_enum (with underscores),
     but db.Enum(SectionTypeEnum) defaulted to looking for "sectiontypeenum"
     (no underscores), causing:
         type "sectiontypeenum" does not exist
     Pointing it at the correct existing name resolves the insert error
     without any database change.
"""

from app.extensions import db
from datetime import datetime
import enum


# ── Enum ──────────────────────────────────────────────────────────────────────

class SectionTypeEnum(str, enum.Enum):
    contact        = "contact"
    summary        = "summary"
    experience     = "experience"
    education      = "education"
    skills         = "skills"
    projects       = "projects"
    certifications = "certifications"
    achievements   = "achievements"
    languages      = "languages"
    interests      = "interests"
    references     = "references"
    other          = "other"


# ── JobDescription ────────────────────────────────────────────────────────────

class JobDescription(db.Model):
    __tablename__ = "job_descriptions"

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title       = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<JobDescription id={self.id} user_id={self.user_id}>"


# ── ResumeAnalysis ────────────────────────────────────────────────────────────

class ResumeAnalysis(db.Model):
    __tablename__ = "resume_analyses"

    id                  = db.Column(db.Integer, primary_key=True)
    resume_id           = db.Column(db.Integer, db.ForeignKey("resumes.id"),          nullable=False)
    user_id             = db.Column(db.Integer, db.ForeignKey("users.id"),             nullable=False)
    overall_score       = db.Column(db.Float,   nullable=True)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    major               = db.Column(db.String(50), nullable=False)
    job_description_id  = db.Column(db.Integer, db.ForeignKey("job_descriptions.id"), nullable=True)

    ats_result      = db.relationship("AtsResult",      backref="analysis", uselist=False, lazy=True)
    recommendations = db.relationship("Recommendation", backref="analysis", lazy=True)

    def __repr__(self):
        return f"<ResumeAnalysis id={self.id} score={self.overall_score}>"


# ── AtsResult ─────────────────────────────────────────────────────────────────

class AtsResult(db.Model):
    __tablename__ = "ats_results"

    id                       = db.Column(db.Integer, primary_key=True)
    analysis_id              = db.Column(db.Integer, db.ForeignKey("resume_analyses.id"),  nullable=False)
    job_description_id       = db.Column(db.Integer, db.ForeignKey("job_descriptions.id"), nullable=True)
    ats_score                = db.Column(db.Float, nullable=True)
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
    missing_sections         = db.Column(db.JSON, nullable=True)
    missing_keywords         = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f"<AtsResult analysis_id={self.analysis_id} ats_score={self.ats_score}>"


# ── ResumeSection ─────────────────────────────────────────────────────────────

class ResumeSection(db.Model):
    __tablename__ = "resume_sections"

    id              = db.Column(db.Integer, primary_key=True)
    resume_id       = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False)
    # FIX: point at the real DB enum type name and never auto-create it.
    section_type    = db.Column(
        db.Enum(SectionTypeEnum, name="section_type_enum", create_type=False),
        nullable=False,
    )
    section_content = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<ResumeSection {self.section_type.value} resume_id={self.resume_id}>"


# ── Recommendation ────────────────────────────────────────────────────────────

class Recommendation(db.Model):
    __tablename__ = "recommendations"

    id          = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey("resume_analyses.id"), nullable=False)
    section_id  = db.Column(db.Integer, db.ForeignKey("resume_sections.id"), nullable=True)
    title       = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    priority    = db.Column(db.Integer, default=2)

    def __repr__(self):
        return f"<Recommendation analysis_id={self.analysis_id} priority={self.priority}>"


# ── ResumeComparison ──────────────────────────────────────────────────────────

class ResumeComparison(db.Model):
    """
    One comparison session per row.

    Matches resume_comparisons table (9 columns):
        id               integer PK
        user_id          integer FK → users.id
        comparison_name  varchar
        created_at       timestamp
        job_description  text
        winner           varchar(1)   ← 'a' or 'b'
        score_a          float
        score_b          float
        verdict          text
    """
    __tablename__ = "resume_comparisons"

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comparison_name = db.Column(db.String(255), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    job_description = db.Column(db.Text,      nullable=True)
    winner          = db.Column(db.String(1),  nullable=True)   # 'a' or 'b'
    score_a         = db.Column(db.Float,      nullable=True)
    score_b         = db.Column(db.Float,      nullable=True)
    verdict         = db.Column(db.Text,       nullable=True)

    resumes = db.relationship(
        "ComparisonResume",
        backref="comparison",
        lazy=True,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<ResumeComparison id={self.id} winner={self.winner}>"


# ── ComparisonResume ──────────────────────────────────────────────────────────

class ComparisonResume(db.Model):
    """
    Individual CV entry within a comparison session.

    Matches comparison_resumes table (6 columns):
        id             integer PK
        comparison_id  integer FK → resume_comparisons.id
        resume_id      integer   ← NULL for temp uploads
        score          float
        resume_label   varchar(1)    ← 'a' or 'b'
        filename       varchar(255)
    """
    __tablename__ = "comparison_resumes"

    id            = db.Column(db.Integer, primary_key=True)
    comparison_id = db.Column(
        db.Integer,
        db.ForeignKey("resume_comparisons.id", ondelete="CASCADE"),
        nullable=False,
    )
    resume_id    = db.Column(db.Integer,      nullable=True)  # NULL — temp upload
    score        = db.Column(db.Float,        nullable=True)
    resume_label = db.Column(db.String(1),    nullable=True)  # 'a' or 'b'
    filename     = db.Column(db.String(255),  nullable=True)

    def __repr__(self):
        return f"<ComparisonResume comparison_id={self.comparison_id} label={self.resume_label}>"