"""
routes/cv_builder_routes.py

CV Builder module — handles Mode 1 (template), Mode 1b (AI-assisted,
section-by-section hints), and Mode 2 (Generate Full Resume with AI).

Endpoints:
    POST   /cv-builder/draft              — create a new draft session
    GET    /cv-builder/draft/<id>         — get full draft with all sections
    PUT    /cv-builder/draft/<id>/section — save/update one section
    DELETE /cv-builder/draft/<id>         — delete a draft
    GET    /cv-builder/drafts             — list all drafts for current user
    POST   /cv-builder/draft/<id>/hint    — get AI hint for a section (Mode 1b)
    POST   /cv-builder/draft/<id>/analyze — run ATS scoring on draft content
    POST   /cv-builder/draft/<id>/export  — export draft to PDF or DOCX
    POST   /cv-builder/import-cv          — parse uploaded CV into builder JSON
    GET    /cv-builder/draft/<id>/progress— section completion stats
    POST   /cv-builder/draft/generate-full— Mode 2: generate full resume with AI
"""

from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.cv_import_service import import_cv_from_file
from app.extensions import db
from app.models.cv_draft import CvDraft
from app.models.cv_draft_section import CvDraftSection
from app.models.analysis import JobDescription
from app.services.cv_builder_service import (
    build_draft_response,
    get_ai_hint_for_section,
    get_autocomplete_suggestion,
    score_draft,
    export_draft,
)
from app.services.cv_generate_service import (
    format_contact_section,
    format_education_section,
    format_experience_fallback,
    format_skills_fallback,
    format_projects_fallback,
    generate_experience_section,
    generate_skills_section,
    generate_projects_section,
    generate_summary_section,
)

cv_builder_bp = Blueprint("cv_builder", __name__, url_prefix="/cv-builder")

# ── Valid values (enforced here since DB uses Text columns) ───────────────────
VALID_MODES    = {"template", "assisted", "ai_full"}
VALID_STATUSES = {"draft", "completed"}
VALID_SECTIONS = {
    "contact", "summary", "experience", "education", "skills",
    "projects", "certifications", "languages", "awards", "volunteer",
}

# Section save order (matches CvDraftSection.position convention)
_SECTION_POSITIONS = {
    "contact":        0,
    "summary":        1,
    "experience":     2,
    "education":      3,
    "skills":         4,
    "projects":       5,
    "certifications": 6,
    "languages":      7,
}


def _upsert_section(draft_id: int, section_type: str, content_json):
    """
    Create or update one CvDraftSection row.

    Mirrors the upsert logic in save_section() — reused by
    generate_full() so each AI-generated section is saved immediately
    as soon as it's ready, without waiting for the whole pipeline to finish.

    NOTE: does not commit — caller is responsible for db.session.commit().
    """
    section = CvDraftSection.query.filter_by(
        draft_id=draft_id, section_type=section_type
    ).first()

    position = _SECTION_POSITIONS.get(section_type, 0)

    if section:
        section.content_json = content_json
        section.position     = position
        section.updated_at   = datetime.utcnow()
    else:
        section = CvDraftSection(
            draft_id=draft_id,
            section_type=section_type,
            position=position,
            content_json=content_json,
        )
        db.session.add(section)


# ─────────────────────────────────────────────────────────────────────────────
# POST /cv-builder/draft
# Create a new draft session
# ─────────────────────────────────────────────────────────────────────────────
@cv_builder_bp.route("/draft", methods=["POST"])
@jwt_required()
def create_draft():
    """
    Create a new CV builder draft session.

    Body (JSON):
        mode               str  — 'template' or 'assisted'
        template_id        int  — 1 to 5
        job_description    str  — required if mode == 'assisted'
    """
    user_id = get_jwt_identity()
    data    = request.get_json()

    if not data:
        return jsonify({"error": "Request body is required."}), 400

    mode        = data.get("mode", "template").strip().lower()
    template_id = data.get("template_id", 1)
    jd_text     = data.get("job_description", "").strip()

    if mode not in VALID_MODES:
        return jsonify({"error": f"Invalid mode. Choose from: {VALID_MODES}"}), 400

    if not isinstance(template_id, int) or not (1 <= template_id <= 5):
        return jsonify({"error": "template_id must be an integer between 1 and 5."}), 400

    # JD is optional — removed mandatory check

    try:
        jd_id = None
        if mode == "assisted" and jd_text:
            jd = JobDescription(
                user_id=user_id,
                title="CV Builder JD",
                description=jd_text,
            )
            db.session.add(jd)
            db.session.flush()
            jd_id = jd.id

        draft = CvDraft(
            user_id=user_id,
            mode=mode,
            template_id=template_id,
            job_description_id=jd_id,
            status="draft",
        )
        db.session.add(draft)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to create draft. Please try again."}), 500

    return jsonify({
        "message": "Draft created successfully.",
        "draft_id":    draft.id,
        "mode":        draft.mode,
        "template_id": draft.template_id,
        "status":      draft.status,
    }), 201


# ─────────────────────────────────────────────────────────────────────────────
# GET /cv-builder/draft/<draft_id>
# Get full draft with all its sections
# ─────────────────────────────────────────────────────────────────────────────
@cv_builder_bp.route("/draft/<int:draft_id>", methods=["GET"])
@jwt_required()
def get_draft(draft_id):
    """Retrieve a draft and all its saved sections."""
    user_id = get_jwt_identity()
    draft   = CvDraft.query.filter_by(id=draft_id, user_id=user_id).first()

    if not draft:
        return jsonify({"error": "Draft not found."}), 404

    return jsonify(build_draft_response(draft)), 200


# ─────────────────────────────────────────────────────────────────────────────
# PUT /cv-builder/draft/<draft_id>/section
# Save or update a single section (auto-save on every field change)
# ─────────────────────────────────────────────────────────────────────────────
@cv_builder_bp.route("/draft/<int:draft_id>/section", methods=["PUT"])
@jwt_required()
def save_section(draft_id):
    """
    Upsert one section in a draft.

    Body (JSON):
        section_type   str   — e.g. 'experience'
        position       int   — render order (0-indexed)
        content_json   dict  — field values for this section
    """
    user_id = get_jwt_identity()
    draft   = CvDraft.query.filter_by(id=draft_id, user_id=user_id).first()

    if not draft:
        return jsonify({"error": "Draft not found."}), 404

    data         = request.get_json()
    section_type = data.get("section_type", "").strip().lower()
    position     = data.get("position", 0)
    content_json = data.get("content_json", {})

    if section_type not in VALID_SECTIONS:
        return jsonify({"error": f"Invalid section_type. Choose from: {VALID_SECTIONS}"}), 400

    if not isinstance(content_json, (dict, list)):
        return jsonify({"error": "content_json must be a JSON object or array."}), 400

    try:
        # Upsert — one row per section type per draft
        section = CvDraftSection.query.filter_by(
            draft_id=draft.id, section_type=section_type
        ).first()

        if section:
            section.content_json = content_json
            section.position     = position
            section.updated_at   = datetime.utcnow()
        else:
            section = CvDraftSection(
                draft_id=draft.id,
                section_type=section_type,
                position=position,
                content_json=content_json,
            )
            db.session.add(section)

        draft.updated_at = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to save section. Please try again."}), 500

    return jsonify({
        "message":      "Section saved.",
        "section_type": section_type,
        "position":     position,
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /cv-builder/draft/<draft_id>
# Delete a draft and all its sections (cascade handles sections)
# ─────────────────────────────────────────────────────────────────────────────
@cv_builder_bp.route("/draft/<int:draft_id>", methods=["DELETE"])
@jwt_required()
def delete_draft(draft_id):
    """Delete a draft session and all associated sections."""
    user_id = get_jwt_identity()
    draft   = CvDraft.query.filter_by(id=draft_id, user_id=user_id).first()

    if not draft:
        return jsonify({"error": "Draft not found."}), 404

    try:
        db.session.delete(draft)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Failed to delete draft."}), 500

    return jsonify({"message": "Draft deleted."}), 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /cv-builder/drafts
# List all drafts for the current user
# ─────────────────────────────────────────────────────────────────────────────
@cv_builder_bp.route("/drafts", methods=["GET"])
@jwt_required()
def list_drafts():
    """Return all CV builder drafts for the logged-in user."""
    user_id = get_jwt_identity()
    drafts  = CvDraft.query.filter_by(user_id=user_id).order_by(
        CvDraft.updated_at.desc()
    ).all()

    return jsonify({
        "drafts": [
            {
                "draft_id":    d.id,
                "mode":        d.mode,
                "template_id": d.template_id,
                "status":      d.status,
                "created_at":  d.created_at.isoformat() if d.created_at else None,
                "updated_at":  d.updated_at.isoformat() if d.updated_at else None,
            }
            for d in drafts
        ],
        "total": len(drafts),
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# POST /cv-builder/draft/<draft_id>/hint
# Get AI hint for a specific section (Mode 1b only)
# ─────────────────────────────────────────────────────────────────────────────
@cv_builder_bp.route("/draft/<int:draft_id>/hint", methods=["POST"])
@jwt_required()
def get_hint(draft_id):
    """
    Generate AI field hints for one section based on the job description.
    Assisted mode only — returns error if draft is in template mode.

    Body (JSON):
        section_type   str  — section to generate hints for
        content_json   dict — current user input for that section (can be partial)
    """
    user_id = get_jwt_identity()
    draft   = CvDraft.query.filter_by(id=draft_id, user_id=user_id).first()

    if not draft:
        return jsonify({"error": "Draft not found."}), 404

    if draft.mode not in ("assisted", "ai_full"):
        return jsonify({"error": "AI hints are only available in assisted mode."}), 400

    data         = request.get_json()
    section_type = data.get("section_type", "").strip().lower()
    content_json = data.get("content_json", {})

    if section_type not in VALID_SECTIONS:
        return jsonify({"error": f"Invalid section_type."}), 400

    # Load the job description text — optional
    jd_text_hint = ""
    if draft.job_description_id:
        jd = JobDescription.query.get(draft.job_description_id)
        if jd:
            jd_text_hint = jd.description

    hint, error = get_ai_hint_for_section(
        section_type=section_type,
        current_content=content_json,
        job_description=jd_text_hint,
    )
    if error:
        return jsonify({"error": f"AI hint failed: {error}"}), 500

    # Persist hint so frontend can re-load it on refresh
    try:
        section = CvDraftSection.query.filter_by(
            draft_id=draft.id, section_type=section_type
        ).first()
        if section:
            section.ai_hint_json = hint
            section.updated_at   = datetime.utcnow()
            db.session.commit()
    except Exception:
        db.session.rollback()
        # Non-fatal — still return the hint to the user

    return jsonify({
        "section_type": section_type,
        "hint":         hint,
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# POST /cv-builder/draft/<draft_id>/analyze
# Run ATS scoring on the draft content
# ─────────────────────────────────────────────────────────────────────────────
@cv_builder_bp.route("/draft/<int:draft_id>/analyze", methods=["POST"])
@jwt_required()
def analyze_draft(draft_id):
    """
    Score the current draft content using the ATS scoring algorithm.

    Body (JSON):
        major   str — industry sector (technology, medical, etc.)
    """
    user_id = get_jwt_identity()
    draft   = CvDraft.query.filter_by(id=draft_id, user_id=user_id).first()

    if not draft:
        return jsonify({"error": "Draft not found."}), 404

    data  = request.get_json() or {}
    major = data.get("major", "").strip().lower()

    if not major:
        return jsonify({"error": "major is required."}), 400

    jd_text = None
    if draft.job_description_id:
        jd = JobDescription.query.get(draft.job_description_id)
        jd_text = jd.description if jd else None

    result, error = score_draft(draft=draft, major=major, jd_text=jd_text)
    if error:
        return jsonify({"error": f"Scoring failed: {error}"}), 500

    return jsonify(result), 200


# ─────────────────────────────────────────────────────────────────────────────
# POST /cv-builder/draft/<draft_id>/autocomplete
# Inline ghost-text autocomplete for a single field
# ─────────────────────────────────────────────────────────────────────────────
@cv_builder_bp.route("/draft/<int:draft_id>/autocomplete", methods=["POST"])
@jwt_required()
def autocomplete(draft_id):
    """
    Return a plain-text autocomplete suggestion for one CV field.
    Used by the ghost-text overlay — Tab to accept, Escape to dismiss.

    Body (JSON):
        field_name       str  — supported field identifier
        current_value    str  — what user has typed so far (can be empty)
        section_context  dict — other filled fields in the same section
    """
    user_id = get_jwt_identity()
    draft   = CvDraft.query.filter_by(id=draft_id, user_id=user_id).first()

    if not draft:
        return jsonify({"error": "Draft not found."}), 404

    data            = request.get_json() or {}
    field_name      = data.get("field_name", "").strip()
    current_value   = data.get("current_value", "").strip()
    section_context = data.get("section_context", {})

    if not field_name:
        return jsonify({"error": "field_name is required."}), 400

    # Allowlist — prevents prompt injection via arbitrary field names
    ALLOWED_FIELDS = {
        "summary_text", "exp_description", "exp_job_title",
        "proj_description", "edu_degree", "edu_field_of_study", "cert_name",
    }
    if field_name not in ALLOWED_FIELDS:
        return jsonify({"suggestion": ""}), 200

    # Skip if field already has substantial content
    if len(current_value) > 120:
        return jsonify({"suggestion": ""}), 200

    # Load JD — optional
    jd_text = ""
    if draft.job_description_id:
        jd = JobDescription.query.get(draft.job_description_id)
        if jd:
            jd_text = jd.description

    suggestion, error = get_autocomplete_suggestion(
        field_name      = field_name,
        current_value   = current_value,
        section_context = section_context if isinstance(section_context, dict) else {},
        job_description = jd_text,
    )

    # Silent fail — empty suggestion is fine, never break UX
    return jsonify({"suggestion": suggestion or ""}), 200


# ─────────────────────────────────────────────────────────────────────────────
# POST /cv-builder/draft/<draft_id>/export
# Export draft to PDF or DOCX
# ─────────────────────────────────────────────────────────────────────────────
@cv_builder_bp.route("/draft/<int:draft_id>/export", methods=["POST"])
@jwt_required()
def export(draft_id):
    """
    Export the draft as a downloadable PDF or DOCX file.

    Body (JSON):
        format   str — 'pdf' or 'docx'
    """
    user_id = get_jwt_identity()
    draft   = CvDraft.query.filter_by(id=draft_id, user_id=user_id).first()

    if not draft:
        return jsonify({"error": "Draft not found."}), 404

    data        = request.get_json() or {}
    file_format = data.get("format", "pdf").strip().lower()

    if file_format not in {"pdf", "docx"}:
        return jsonify({"error": "format must be 'pdf' or 'docx'."}), 400

    file_path, error = export_draft(draft=draft, file_format=file_format)
    if error:
        return jsonify({"error": f"Export failed: {error}"}), 500

    from flask import send_file
    return send_file(
        file_path,
        as_attachment=True,
        download_name=f"cv_draft_{draft.id}.{file_format}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /cv-builder/import-cv
# Accept a CV file upload and return structured builder JSON
# ─────────────────────────────────────────────────────────────────────────────
@cv_builder_bp.route("/import-cv", methods=["POST"])
@jwt_required()
def import_cv():
    """
    Parse an uploaded CV file and return structured JSON that matches
    the builder's content_json schemas — ready to pre-fill all fields.

    Request: multipart/form-data with field 'file' (PDF or DOCX, max 5MB)

    Response:
        {
          "contact":        {...},
          "summary":        {...},
          "experience":     [...],
          "education":      [...],
          "skills":         [...],
          "projects":       [...],
          "certifications": [...],
          "languages":      [...]
        }
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Send the file in the 'file' field."}), 400

    file = request.files["file"]

    if not file or file.filename == "":
        return jsonify({"error": "No file selected."}), 400

    # 5 MB limit — check content length header if present
    file.seek(0, 2)          # seek to end
    file_size = file.tell()  # get size in bytes
    file.seek(0)             # reset

    if file_size > 5 * 1024 * 1024:
        return jsonify({"error": "File too large. Maximum size is 5 MB."}), 413

    structured, error = import_cv_from_file(file)
    if error:
        return jsonify({"error": error}), 422

    return jsonify(structured), 200


# ─────────────────────────────────────────────────────────────────────────────
# GET /cv-builder/draft/<draft_id>/progress
# Section completion stats for the progress bar
# ─────────────────────────────────────────────────────────────────────────────
@cv_builder_bp.route("/draft/<int:draft_id>/progress", methods=["GET"])
@jwt_required()
def get_progress(draft_id):
    """
    Return section completion stats for the progress bar.
    Cheap — no NLP, no LLM, just counts filled sections.
    """
    user_id = get_jwt_identity()
    draft   = CvDraft.query.filter_by(id=draft_id, user_id=user_id).first()

    if not draft:
        return jsonify({"error": "Draft not found."}), 404

    CORE_SECTIONS = ["contact", "summary", "experience", "education", "skills", "projects", "certifications"]

    sections = CvDraftSection.query.filter_by(draft_id=draft.id).all()
    filled   = {s.section_type for s in sections if s.content_json}

    completed = [s for s in CORE_SECTIONS if s in filled]

    return jsonify({
        "total":     len(CORE_SECTIONS),
        "completed": len(completed),
        "sections":  {s: (s in filled) for s in CORE_SECTIONS},
        "percent":   round(len(completed) / len(CORE_SECTIONS) * 100),
    }), 200


# ─────────────────────────────────────────────────────────────────────────────
# POST /cv-builder/draft/generate-full
# Mode 2 — "Generate Full Resume with AI"
# ─────────────────────────────────────────────────────────────────────────────
@cv_builder_bp.route("/draft/generate-full", methods=["POST"])
@jwt_required()
def generate_full():
    """
    Generate a complete, ATS-optimized resume from wizard facts + a job
    description, one section at a time.

    Body (JSON):
        major            str   — industry sector (technology, medical, etc.)
                                  Optional; defaults to 'technology' for scoring.
        target_title     str   — the role the user is applying for (used to
                                  steer tone of summary/experience bullets)
        job_description  str   — REQUIRED. The JD pasted by the user.
        contact          dict  — {name, email, phone, location, linkedin, website}
        education        list  — [{degree, institution, field_of_study, end_date, gpa}]
        experience       list  — [{job_title, company, start_date, end_date, notes}]
        skills           list  — flat list of raw skill name strings
        projects         list  — [{title, tech_stack, notes, url}] (optional)
        certifications   list  — [{name, issuer, date}] (optional, passthrough)
        languages        list  — [{language, proficiency}] (optional, passthrough)

    Generation order (each section saved immediately after generation,
    so a partial failure still leaves a usable draft):
        1. contact         (no AI — facts only)
        2. education        (no AI — facts only)
        3. experience       (AI — bullets per job, 1 call)
        4. skills           (AI — categorization, 1 call)
        5. projects         (AI — descriptions per project, 1 call, skipped if empty)
        6. summary          (AI — written last, uses 3-5 as context, 1 call)
        7. certifications / languages (passthrough, no AI)

    Returns:
        {
          "draft_id": 12,
          "sections": { ...all generated content_json by section_type... },
          "score": { ...same shape as /draft/<id>/analyze... } or null,
          "generation_errors": { "experience": "..." } or null
        }
    """
    user_id = get_jwt_identity()
    data    = request.get_json()

    if not data:
        return jsonify({"error": "Request body is required."}), 400

    jd_text = (data.get("job_description") or "").strip()
    if not jd_text:
        return jsonify({"error": "Job description is required."}), 400

    contact = data.get("contact") or {}
    if not (contact.get("name") or "").strip():
        return jsonify({"error": "Your name is required."}), 400
    if not (contact.get("email") or "").strip():
        return jsonify({"error": "Your email is required."}), 400

    major         = (data.get("major") or "").strip().lower() or "technology"
    target_title  = (data.get("target_title") or "").strip()
    education_in  = data.get("education") or []
    experience_in = data.get("experience") or []
    skills_in     = data.get("skills") or []
    projects_in   = data.get("projects") or []
    certifications_in = data.get("certifications") or []
    languages_in       = data.get("languages") or []

    # ── 1. Create the JobDescription + CvDraft rows ──────────────────────────
    try:
        jd = JobDescription(
            user_id=user_id,
            title="AI Full Generate JD",
            description=jd_text,
        )
        db.session.add(jd)
        db.session.flush()

        draft = CvDraft(
            user_id=user_id,
            mode="ai_full",
            template_id=1,
            job_description_id=jd.id,
            status="draft",
        )
        db.session.add(draft)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to create draft. Please try again."}), 500

    generated = {}
    errors    = {}

    # ── 2. Contact — facts only, no AI ───────────────────────────────────────
    generated["contact"] = format_contact_section(contact)
    _upsert_section(draft.id, "contact", generated["contact"])

    # ── 3. Education — facts only, no AI ─────────────────────────────────────
    generated["education"] = format_education_section(education_in)
    _upsert_section(draft.id, "education", generated["education"])

    # ── 4. Experience — AI bullets per job ───────────────────────────────────
    exp_result, exp_err = generate_experience_section(experience_in, jd_text, target_title)
    if exp_err:
        errors["experience"] = exp_err
        exp_result = format_experience_fallback(experience_in)
    generated["experience"] = exp_result
    _upsert_section(draft.id, "experience", generated["experience"])

    # ── 5. Skills — AI categorization ────────────────────────────────────────
    skills_result, skills_err = generate_skills_section(skills_in, jd_text)
    if skills_err:
        errors["skills"] = skills_err
        skills_result = format_skills_fallback(skills_in)
    generated["skills"] = skills_result
    _upsert_section(draft.id, "skills", generated["skills"])

    # ── 6. Projects — AI descriptions per project (skipped if none given) ────
    proj_result, proj_err = generate_projects_section(projects_in, jd_text)
    if proj_err:
        errors["projects"] = proj_err
        proj_result = format_projects_fallback(projects_in)
    generated["projects"] = proj_result
    _upsert_section(draft.id, "projects", generated["projects"])

    # ── 7. Summary — AI, written last so it can reference everything above ──
    summary_result, summary_err = generate_summary_section(
        contact=generated["contact"],
        target_title=target_title,
        experience=generated["experience"],
        education=generated["education"],
        skills=generated["skills"],
        jd_text=jd_text,
    )
    if summary_err:
        errors["summary"] = summary_err
        summary_result = {"text": ""}
    generated["summary"] = summary_result
    _upsert_section(draft.id, "summary", generated["summary"])

    # ── 8. Certifications / Languages — passthrough, no AI ──────────────────
    generated["certifications"] = certifications_in
    generated["languages"]      = languages_in
    _upsert_section(draft.id, "certifications", certifications_in)
    _upsert_section(draft.id, "languages", languages_in)

    # ── Commit all sections ──────────────────────────────────────────────────
    try:
        draft.updated_at = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Failed to save generated sections."}), 500

    # ── 9. Initial ATS score (best-effort — don't fail the whole request) ───
    score_result = None
    try:
        score_result, score_err = score_draft(draft=draft, major=major, jd_text=jd_text)
        if score_err:
            errors["score"] = score_err
            score_result = None
    except Exception as e:
        errors["score"] = str(e)

    return jsonify({
        "draft_id":          draft.id,
        "sections":          generated,
        "score":             score_result,
        "generation_errors": errors or None,
    }), 201