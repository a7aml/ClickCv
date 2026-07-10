"""
routes/rebuild_routes.py

Handles the CV rebuild feature.

FIX: Added _merge_sections() to prevent the LLM from silently
     dropping sections like 'languages' and 'projects'.
     Called after generate_rebuilt_cv() in both routes.
"""

import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.resume import Resume
from app.models.analysis import ResumeAnalysis, AtsResult, JobDescription
from app.models.generated_cv import GeneratedCv
from app.services.nlp_service import detect_sections, extract_keywords_per_section
from app.services.scoring_service import calculate_ats_score
from app.services.llm_service import generate_rebuilt_cv

build_bp = Blueprint("build", __name__, url_prefix="/build")

# Canonical section display order
SECTION_ORDER = [
    "contact", "summary", "experience", "education",
    "skills", "projects", "certifications", "languages",
    "achievements", "interests",
]


def _band(score: float) -> str:
    if score >= 75: return "strong"
    if score >= 65: return "good"
    if score >= 50: return "borderline"
    return "weak"


def _extract_scores(scoring_result: dict) -> dict:
    keys = [
        "keyword_score", "keyword_placement_score", "formatting_score",
        "structure_score", "experience_recency_score", "achievements_score",
        "job_title_score", "education_score", "resume_length_score",
        "contact_info_score",
    ]
    return {k: round(scoring_result.get(k) or 0, 1) for k in keys}


def _merge_sections(original: dict, rebuilt: dict) -> dict:
    """
    Merge LLM-rebuilt sections with the originals.

    - If the LLM returned a section  → use the rebuilt version.
    - If the LLM omitted a section that existed in original → restore original.
    - Order follows SECTION_ORDER, then any extra keys alphabetically.
    - Empty/whitespace-only values are treated as absent.

    Safety net: even if the LLM prompt fix fails, this ensures no section
    is ever lost from the final output.
    """
    merged = {}

    for key in SECTION_ORDER:
        rebuilt_val  = (rebuilt.get(key)  or "").strip()
        original_val = (original.get(key) or "").strip()

        if rebuilt_val:
            merged[key] = rebuilt_val
        elif original_val:
            merged[key] = original_val

    # Any extra keys not in SECTION_ORDER
    extra_keys = sorted(
        set(list(original.keys()) + list(rebuilt.keys())) - set(SECTION_ORDER)
    )
    for key in extra_keys:
        rebuilt_val  = (rebuilt.get(key)  or "").strip()
        original_val = (original.get(key) or "").strip()
        if rebuilt_val:
            merged[key] = rebuilt_val
        elif original_val:
            merged[key] = original_val

    return merged


def _weighted_overall(scoring: dict) -> float:
    weights = {
        "keyword_score": 0.35, "keyword_placement_score": 0.18,
        "formatting_score": 0.17, "structure_score": 0.12,
        "experience_recency_score": 0.10, "achievements_score": 0.10,
        "job_title_score": 0.08, "education_score": 0.07,
        "resume_length_score": 0.04, "contact_info_score": 0.03,
    }
    return min(round(sum(scoring.get(k, 0) * w for k, w in weights.items()), 1), 100.0)


# ═══════════════════════════════════════════════════════════════════
# POST /build/rebuild  — from analysis_id (history page)
# ═══════════════════════════════════════════════════════════════════
@build_bp.route("/rebuild", methods=["POST"])
@jwt_required()
def rebuild_cv():
    user_id = get_jwt_identity()
    data    = request.get_json()

    if not data or not data.get("analysis_id"):
        return jsonify({"error": "analysis_id is required."}), 400

    analysis_id = int(data["analysis_id"])

    analysis = ResumeAnalysis.query.filter_by(id=analysis_id, user_id=user_id).first()
    if not analysis:
        return jsonify({"error": "Analysis not found."}), 404

    resume = Resume.query.get(analysis.resume_id)
    if not resume:
        return jsonify({"error": "Original resume not found."}), 404

    if not resume.raw_text:
        return jsonify({"error": "Original resume text is missing. Please re-upload and re-analyse your CV."}), 422

    existing = GeneratedCv.query.filter_by(analysis_id=analysis_id).first()
    if existing:
        return jsonify({
            "message": "Rebuild already exists for this analysis.",
            "generated_id": existing.id,
            "already_exists": True,
            **_build_response_payload(existing, analysis),
        }), 200

    ats = AtsResult.query.filter_by(analysis_id=analysis_id).first()
    if not ats:
        return jsonify({"error": "ATS result not found. Please re-analyse your CV first."}), 422

    scoring_result = {
        "overall_score":            round(ats.ats_score or 0, 1),
        "score_band":               _band(ats.ats_score or 0),
        "keyword_score":            ats.keyword_score,
        "keyword_placement_score":  ats.keyword_placement_score,
        "formatting_score":         ats.formatting_score,
        "structure_score":          ats.structure_score,
        "experience_recency_score": ats.experience_recency_score,
        "achievements_score":       ats.achievements_score,
        "job_title_score":          ats.job_title_score,
        "education_score":          ats.education_score,
        "resume_length_score":      ats.resume_length_score,
        "contact_info_score":       ats.contact_info_score,
        "missing_sections":         ats.missing_sections or [],
        "missing_keywords":         ats.missing_keywords or [],
        "used_jd":                  bool(analysis.job_description_id),
    }

    job_description = None
    if analysis.job_description_id:
        jd = JobDescription.query.get(analysis.job_description_id)
        if jd:
            job_description = jd.description

    sections = resume.parsed_data or {}
    if not sections:
        sections, error = detect_sections(resume.raw_text)
        if error or not sections:
            sections = {}

    rebuilt_sections_raw, error = generate_rebuilt_cv(
        raw_text=resume.raw_text,
        sections=sections,
        scoring_result=scoring_result,
        major=analysis.major,
        job_description=job_description,
    )
    if error:
        current_app.logger.error(f"Rebuild LLM failed for analysis {analysis_id}: {error}")
        return jsonify({"error": f"CV rebuild failed: {error}"}), 422

    rebuilt_sections = _merge_sections(sections, rebuilt_sections_raw)
    current_app.logger.info(
        f"Rebuild [{analysis_id}] — original: {list(sections.keys())} | "
        f"LLM: {list(rebuilt_sections_raw.keys())} | "
        f"merged: {list(rebuilt_sections.keys())}"
    )

    rebuilt_text = "\n\n".join(f"{k.upper()}\n{v}" for k, v in rebuilt_sections.items())
    rebuilt_keyword_placement, _ = extract_keywords_per_section(rebuilt_sections)
    rebuilt_keyword_placement = rebuilt_keyword_placement or {}

    rebuilt_scoring, error = calculate_ats_score(
        raw_text=rebuilt_text,
        sections=rebuilt_sections,
        keyword_placement=rebuilt_keyword_placement,
        major=analysis.major,
        job_description=job_description,
        file_path=None,
    )
    if error:
        current_app.logger.error(f"Re-scoring failed for analysis {analysis_id}: {error}")
        return jsonify({"error": f"Re-scoring rebuilt CV failed: {error}"}), 422

    rebuilt_scoring["formatting_score"] = 100.0
    corrected_overall = _weighted_overall(rebuilt_scoring)
    rebuilt_scoring["overall_score"] = corrected_overall
    rebuilt_scoring["score_band"]    = _band(corrected_overall)

    original_score = round(analysis.overall_score or 0, 1)
    rebuilt_score  = round(corrected_overall, 1)
    score_delta    = round(rebuilt_score - original_score, 1)
    rebuilt_scores = _extract_scores(rebuilt_scoring)

    try:
        generated = GeneratedCv(
            user_id=user_id, resume_id=analysis.resume_id, analysis_id=analysis_id,
            sections_json=rebuilt_sections, original_score=original_score,
            rebuilt_score=rebuilt_score, score_delta=score_delta,
            keyword_score=rebuilt_scores["keyword_score"],
            keyword_placement_score=rebuilt_scores["keyword_placement_score"],
            formatting_score=rebuilt_scores["formatting_score"],
            structure_score=rebuilt_scores["structure_score"],
            experience_recency_score=rebuilt_scores["experience_recency_score"],
            achievements_score=rebuilt_scores["achievements_score"],
            job_title_score=rebuilt_scores["job_title_score"],
            education_score=rebuilt_scores["education_score"],
            resume_length_score=rebuilt_scores["resume_length_score"],
            contact_info_score=rebuilt_scores["contact_info_score"],
            missing_keywords=rebuilt_scoring.get("missing_keywords", []),
            missing_sections=rebuilt_scoring.get("missing_sections", []),
        )
        db.session.add(generated)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"DB save failed for generated CV (analysis {analysis_id}): {e}")
        return jsonify({"error": "Failed to save rebuilt CV. Please try again."}), 500

    current_app.logger.info(
        f"CV rebuilt for analysis {analysis_id}: {original_score} → {rebuilt_score} (Δ{score_delta:+.1f})"
    )

    return jsonify({
        "message": "CV rebuilt successfully.",
        "generated_id": generated.id,
        "already_exists": False,
        **_build_response_payload(generated, analysis),
    }), 200


# ═══════════════════════════════════════════════════════════════════
# GET /build/result/<generated_id>
# ═══════════════════════════════════════════════════════════════════
@build_bp.route("/result/<int:generated_id>", methods=["GET"])
@jwt_required()
def get_rebuild_result(generated_id):
    user_id   = get_jwt_identity()
    generated = GeneratedCv.query.filter_by(id=generated_id, user_id=user_id).first()
    if not generated:
        return jsonify({"error": "Rebuilt CV not found."}), 404
    analysis = ResumeAnalysis.query.get(generated.analysis_id)
    return jsonify({"generated_id": generated.id, **_build_response_payload(generated, analysis)}), 200


# ═══════════════════════════════════════════════════════════════════
# GET /build/check/<analysis_id>
# ═══════════════════════════════════════════════════════════════════
@build_bp.route("/check/<int:analysis_id>", methods=["GET"])
@jwt_required()
def check_rebuild_exists(analysis_id):
    user_id   = get_jwt_identity()
    generated = GeneratedCv.query.filter_by(analysis_id=analysis_id, user_id=user_id).first()
    if generated:
        return jsonify({
            "exists": True,
            "generated_id": generated.id,
            "rebuilt_score": generated.rebuilt_score,
            "score_delta":   generated.score_delta,
        }), 200
    return jsonify({"exists": False}), 200


# ═══════════════════════════════════════════════════════════════════
# POST /build/rebuild-upload  — direct file upload (no prior analysis)
# ═══════════════════════════════════════════════════════════════════
@build_bp.route("/rebuild-upload", methods=["POST"])
@jwt_required()
def rebuild_cv_upload():
    """
    Rebuild a CV from a direct file upload — no prior analysis needed.

    Request: multipart/form-data
        file            — PDF or DOCX (required)
        major           — industry sector (required)
        job_description — JD text (optional)
    """
    user_id = get_jwt_identity()

    if "file" not in request.files:
        return jsonify({"error": "CV file is required."}), 400

    file  = request.files["file"]
    major = request.form.get("major", "").strip().lower()
    jd    = request.form.get("job_description", "").strip()

    if not file or file.filename == "":
        return jsonify({"error": "No file selected."}), 400
    if not major:
        return jsonify({"error": "major is required."}), 400

    ext = os.path.splitext(secure_filename(file.filename))[1].lower()
    if ext not in {".pdf", ".docx"}:
        return jsonify({"error": "Only PDF and DOCX files are supported."}), 400

    upload_folder = current_app.config.get(
        "UPLOAD_FOLDER",
        os.path.abspath(os.path.join(current_app.root_path, "static", "uploads"))
    )
    os.makedirs(upload_folder, exist_ok=True)
    tmp_filename = f"rebuild_{user_id}_{uuid.uuid4().hex[:8]}{ext}"
    tmp_path     = os.path.abspath(os.path.join(upload_folder, tmp_filename))
    file.save(tmp_path)

    try:
        from app.services.extraction_service import extract_text_from_file
        raw_text, error = extract_text_from_file(tmp_path)
        if error or not raw_text or not raw_text.strip():
            return jsonify({"error": "Could not extract text from file. Is it a text-based PDF?"}), 422

        sections, error = detect_sections(raw_text)
        if error or not sections:
            sections = {}

        current_app.logger.info(
            f"rebuild-upload [{user_id}] detected sections: {list(sections.keys())}"
        )

        keyword_placement, _ = extract_keywords_per_section(sections)
        keyword_placement = keyword_placement or {}

        original_scoring, error = calculate_ats_score(
            raw_text=raw_text, sections=sections,
            keyword_placement=keyword_placement,
            major=major, job_description=jd or None, file_path=tmp_path,
        )
        if error:
            return jsonify({"error": f"Scoring failed: {error}"}), 422

        original_score = round(original_scoring.get("overall_score", 0), 1)
        scoring_result = {
            **original_scoring,
            "score_band":       _band(original_score),
            "missing_sections": original_scoring.get("missing_sections", []),
            "missing_keywords": original_scoring.get("missing_keywords", []),
            "used_jd":          bool(jd),
        }

        rebuilt_sections_raw, error = generate_rebuilt_cv(
            raw_text=raw_text, sections=sections,
            scoring_result=scoring_result,
            major=major, job_description=jd or None,
        )
        if error:
            return jsonify({"error": f"CV rebuild failed: {error}"}), 422

        current_app.logger.info(
            f"rebuild-upload [{user_id}] LLM returned: {list(rebuilt_sections_raw.keys())}"
        )

        rebuilt_sections = _merge_sections(sections, rebuilt_sections_raw)

        current_app.logger.info(
            f"rebuild-upload [{user_id}] merged: {list(rebuilt_sections.keys())}"
        )

        rebuilt_text = "\n\n".join(
            f"{k.upper()}\n{v}" for k, v in rebuilt_sections.items()
        )
        rebuilt_kp, _ = extract_keywords_per_section(rebuilt_sections)
        rebuilt_kp = rebuilt_kp or {}

        rebuilt_scoring, error = calculate_ats_score(
            raw_text=rebuilt_text, sections=rebuilt_sections,
            keyword_placement=rebuilt_kp,
            major=major, job_description=jd or None, file_path=None,
        )
        if error:
            return jsonify({"error": f"Re-scoring failed: {error}"}), 422

        rebuilt_scoring["formatting_score"] = 100.0
        corrected = _weighted_overall(rebuilt_scoring)
        rebuilt_scoring["overall_score"] = corrected
        rebuilt_scoring["score_band"]    = _band(corrected)

        rebuilt_score = corrected
        score_delta   = round(rebuilt_score - original_score, 1)

        return jsonify({
            "message":          "CV rebuilt successfully.",
            "already_exists":   False,
            "sections":         rebuilt_sections,
            "original_score":   original_score,
            "rebuilt_score":    rebuilt_score,
            "score_delta":      score_delta,
            "score_band":       _band(rebuilt_score),
            "major":            major,
            "original_scores":  _extract_scores(original_scoring),
            "rebuilt_scores":   _extract_scores(rebuilt_scoring),
            "missing_keywords": rebuilt_scoring.get("missing_keywords", []),
            "missing_sections": rebuilt_scoring.get("missing_sections", []),
        }), 200

    except Exception as e:
        import traceback
        current_app.logger.error(
            f"rebuild_cv_upload failed: {e}\n{traceback.format_exc()}"
        )
        return jsonify({"error": "Rebuild failed. Please try again."}), 500

    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# Helper — build the full response payload from a GeneratedCv row
# ═══════════════════════════════════════════════════════════════════
def _build_response_payload(generated: GeneratedCv, analysis: ResumeAnalysis) -> dict:
    original_ats = AtsResult.query.filter_by(analysis_id=generated.analysis_id).first()
    return {
        "sections":        generated.sections_json,
        "original_score":  generated.original_score,
        "rebuilt_score":   generated.rebuilt_score,
        "score_delta":     generated.score_delta,
        "score_band":      _band(generated.rebuilt_score or 0),
        "analysis_id":     generated.analysis_id,
        "resume_id":       generated.resume_id,
        "major":           analysis.major if analysis else None,
        "created_at":      generated.created_at.isoformat(),
        "original_scores": {
            "keyword_score":            original_ats.keyword_score            if original_ats else 0,
            "keyword_placement_score":  original_ats.keyword_placement_score  if original_ats else 0,
            "formatting_score":         original_ats.formatting_score         if original_ats else 0,
            "structure_score":          original_ats.structure_score          if original_ats else 0,
            "experience_recency_score": original_ats.experience_recency_score if original_ats else 0,
            "achievements_score":       original_ats.achievements_score       if original_ats else 0,
            "job_title_score":          original_ats.job_title_score          if original_ats else 0,
            "education_score":          original_ats.education_score          if original_ats else 0,
            "resume_length_score":      original_ats.resume_length_score      if original_ats else 0,
            "contact_info_score":       original_ats.contact_info_score       if original_ats else 0,
        },
        "rebuilt_scores": {
            "keyword_score":            generated.keyword_score,
            "keyword_placement_score":  generated.keyword_placement_score,
            "formatting_score":         generated.formatting_score,
            "structure_score":          generated.structure_score,
            "experience_recency_score": generated.experience_recency_score,
            "achievements_score":       generated.achievements_score,
            "job_title_score":          generated.job_title_score,
            "education_score":          generated.education_score,
            "resume_length_score":      generated.resume_length_score,
            "contact_info_score":       generated.contact_info_score,
        },
        "missing_keywords": generated.missing_keywords or [],
        "missing_sections": generated.missing_sections or [],
    }