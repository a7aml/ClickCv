"""
models/analysis.py

SQLAlchemy models matching the exact DB schema from pgAdmin.

Tables covered:
    resume_analyses   — one analysis session per row
    ats_results       — 10 criterion scores per analysis
    resume_sections   — one row per detected section per resume
    recommendations   — LLM-generated recommendations per analysis
    job_descriptions  — stored JD text per user
"""

from app.extensions import db
from datetime import datetime
import enum


# ── Enum — matches section_type_enum in PostgreSQL ───────────────────────────

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
    """
    Stores raw job description text submitted by the user.
    Linked to resume_analyses via job_description_id FK.

    Columns match pgAdmin:
        id          integer PK
        user_id     integer FK → users.id
        title       varchar(255)
        description text
        created_at  timestamp
    """
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
    """
    One analysis session per row.

    Columns match pgAdmin:
        id                 integer PK
        resume_id          integer FK → resumes.id
        user_id            integer FK → users.id
        overall_score      double precision
        created_at         timestamp
        major              varchar(50)
        job_description_id integer FK → job_descriptions.id
    """
    __tablename__ = "resume_analyses"

    id                  = db.Column(db.Integer, primary_key=True)
    resume_id           = db.Column(db.Integer, db.ForeignKey("resumes.id"),          nullable=False)
    user_id             = db.Column(db.Integer, db.ForeignKey("users.id"),             nullable=False)
    overall_score       = db.Column(db.Float,   nullable=True)
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    major               = db.Column(db.String(50), nullable=False)
    job_description_id  = db.Column(db.Integer, db.ForeignKey("job_descriptions.id"), nullable=True)

    # Relationships
    ats_result      = db.relationship("AtsResult",      backref="analysis", uselist=False, lazy=True)
    recommendations = db.relationship("Recommendation", backref="analysis", lazy=True)

    def __repr__(self):
        return f"<ResumeAnalysis id={self.id} score={self.overall_score}>"


# ── AtsResult ─────────────────────────────────────────────────────────────────

class AtsResult(db.Model):
    """
    Stores all 10 individual criterion scores for one analysis.

    Columns match pgAdmin exactly (16 columns total):
        id                       integer PK
        analysis_id              integer FK → resume_analyses.id
        job_description_id       integer FK → job_descriptions.id
        ats_score                double precision  ← final composite
        keyword_score            double precision  ← criterion 1
        formatting_score         double precision  ← criterion 3
        structure_score          double precision  ← criterion 4
        missing_sections         jsonb
        missing_keywords         jsonb
        keyword_placement_score  double precision  ← criterion 2
        experience_recency_score double precision  ← criterion 5
        achievements_score       double precision  ← criterion 6
        job_title_score          double precision  ← criterion 7
        education_score          double precision  ← criterion 8
        resume_length_score      double precision  ← criterion 9
        contact_info_score       double precision  ← criterion 10
    """
    __tablename__ = "ats_results"

    id                       = db.Column(db.Integer, primary_key=True)
    analysis_id              = db.Column(db.Integer, db.ForeignKey("resume_analyses.id"), nullable=False)
    job_description_id       = db.Column(db.Integer, db.ForeignKey("job_descriptions.id"), nullable=True)

    # Final composite score
    ats_score                = db.Column(db.Float, nullable=True)

    # 10 individual criterion scores
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

    # JSON arrays for frontend display
    missing_sections         = db.Column(db.JSON, nullable=True)
    missing_keywords         = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f"<AtsResult analysis_id={self.analysis_id} ats_score={self.ats_score}>"


# ── ResumeSection ─────────────────────────────────────────────────────────────

class ResumeSection(db.Model):
    """
    One detected section per row per resume.

    Columns match pgAdmin (4 columns):
        id              integer PK
        resume_id       integer FK → resumes.id
        section_type    section_type_enum
        section_content text
    """
    __tablename__ = "resume_sections"

    id              = db.Column(db.Integer, primary_key=True)
    resume_id       = db.Column(db.Integer, db.ForeignKey("resumes.id"), nullable=False)
    section_type    = db.Column(db.Enum(SectionTypeEnum), nullable=False)
    section_content = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<ResumeSection {self.section_type.value} resume_id={self.resume_id}>"


# ── Recommendation ────────────────────────────────────────────────────────────

class Recommendation(db.Model):
    """
    LLM-generated recommendation per section per analysis.

    Columns match pgAdmin (6 columns):
        id          integer PK
        analysis_id integer FK → resume_analyses.id
        section_id  integer FK → resume_sections.id
        title       varchar(255)
        description text
        priority    integer  (1=critical, 2=important, 3=minor)
    """
    __tablename__ = "recommendations"

    id          = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey("resume_analyses.id"), nullable=False)
    section_id  = db.Column(db.Integer, db.ForeignKey("resume_sections.id"), nullable=True)
    title       = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    priority    = db.Column(db.Integer, default=2)

    def __repr__(self):
        return f"<Recommendation analysis_id={self.analysis_id} priority={self.priority}>"