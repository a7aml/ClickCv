"""
routes/analysis_routes.py

SCORE-FIRST SPLIT:
  /analysis/run                       — extract + sections + keybert + scoring,
                                        saves analysis to DB, returns score
                                        IMMEDIATELY. Does NOT call GPT. (~1.5s)
  /analysis/recommendations/<id>      — runs ONLY the GPT recommendations call
                                        for an existing analysis, saves the
                                        recommendation rows, returns them. (~11-19s)

The frontend calls /run first (fast → shows score), then calls
/recommendations in the background (slow → cards animate in when ready).

CV PREVIEW additions:
  - raw_text       returned so the frontend can render the actual CV text
  - sections_data  returned so the preview knows section boundaries
  - found_keywords returned so the preview can highlight present keywords in blue
"""

import os
import uuid
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.extensions import db
from app.models.user import User
from app.models.resume import Resume
from app.models.analysis import (
    ResumeAnalysis, AtsResult, ResumeSection,
    Recommendation, SectionTypeEnum,
)
from app.utils.file_validators import validate_cv_file
from app.services.extraction_service import extract_text_from_file
from app.services.nlp_service import (
    detect_sections, extract_keywords_per_section, get_missing_sections,
)
from app.services.scoring_service import calculate_ats_score
from app.services.llm_service import generate_recommendations

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")


@analysis_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload_cv():
    """Validate and store an uploaded CV file."""
    user_id = get_jwt_identity()
    if "file" not in request.files:
        return jsonify({"error": "No file was included in the request."}), 400
    file  = request.files["file"]

    major = request.form.get("major", "").strip().lower()
    auto_detect = request.form.get("auto_detect", "false").lower() == "true"

    if not major and not auto_detect:
        return jsonify({"error": "Please select your industry major."}), 400

    if auto_detect:
        upload_folder = current_app.config.get("UPLOAD_FOLDER", "app/static/uploads")
        os.makedirs(upload_folder, exist_ok=True)
        temp_path = os.path.join(upload_folder, f"temp_{user_id}_{uuid.uuid4().hex}.{file.filename.rsplit('.', 1)[-1].lower()}")
        try:
            file.save(temp_path)
            raw_text, extract_error = extract_text_from_file(temp_path)

            if not extract_error and raw_text:
                text_lower = raw_text.lower()

                medical_keywords = ['medical', 'doctor', 'nurse', 'patient', 'hospital', 'clinical', 'healthcare', 'physician', 'surgery', 'diagnosis']
                medical_count = sum(1 for kw in medical_keywords if kw in text_lower)

                engineering_keywords = ['engineer', 'civil', 'mechanical', 'electrical', 'construction', 'design', 'cad', 'autocad', 'structural']
                engineering_count = sum(1 for kw in engineering_keywords if kw in text_lower)

                financial_keywords = ['finance', 'accounting', 'audit', 'banking', 'investment', 'financial', 'tax', 'budget', 'excel', 'quickbooks']
                financial_count = sum(1 for kw in financial_keywords if kw in text_lower)

                marketing_keywords = ['marketing', 'social media', 'seo', 'content', 'campaign', 'brand', 'digital marketing', 'analytics', 'advertising']
                marketing_count = sum(1 for kw in marketing_keywords if kw in text_lower)

                tech_keywords = ['python', 'java', 'javascript', 'software', 'developer', 'programming', 'database', 'api', 'cloud', 'aws', 'react', 'node']
                tech_count = sum(1 for kw in tech_keywords if kw in text_lower)

                counts = {
                    'medical': medical_count,
                    'engineering': engineering_count,
                    'financial': financial_count,
                    'marketing': marketing_count,
                    'technology': tech_count
                }
                major = max(counts, key=counts.get)
            else:
                major = "technology"

            if os.path.exists(temp_path):
                os.remove(temp_path)

        except Exception as e:
            current_app.logger.error(f"Auto-detection failed: {e}")
            major = "technology"
            if os.path.exists(temp_path):
                os.remove(temp_path)

    valid_majors = {"technology", "medical", "engineering", "financial", "marketing"}
    if major not in valid_majors:
        return jsonify({"error": "Invalid industry major selected."}), 400
    is_valid, error = validate_cv_file(file)
    if not is_valid:
        return jsonify({"error": error}), 400
    ext           = file.filename.rsplit(".", 1)[-1].lower()
    safe_filename = f"{user_id}_{uuid.uuid4().hex}.{ext}"
    upload_folder = current_app.config.get("UPLOAD_FOLDER", "app/static/uploads")
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, safe_filename)
    try:
        if auto_detect:
            file.seek(0)
        file.save(file_path)
    except Exception as e:
        current_app.logger.error(f"File save failed for user {user_id}: {e}")
        return jsonify({"error": "Failed to save the file. Please try again."}), 500
    job_description = request.form.get("job_description", "").strip()
    try:
        resume = Resume(
            user_id=user_id, file_name=file.filename,
            file_path=file_path, raw_text=None, parsed_data=None,
        )
        db.session.add(resume)
        db.session.commit()
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        current_app.logger.error(f"Resume DB insert failed: {e}")
        return jsonify({"error": "Failed to save the resume. Please try again."}), 500
    return jsonify({
        "message": "CV uploaded successfully.", "resume_id": resume.id,
        "original_filename": file.filename, "major": major,
        "has_job_description": bool(job_description),
    }), 201


@analysis_bp.route("/run", methods=["POST"])
@jwt_required()
def run_analysis():
    """
    PHASE 1 — Fast scoring only (NO GPT call).

    Runs extract → sections → keybert → ATS scoring, saves the analysis
    + ATS result + sections to the DB, and returns the score immediately.

    Recommendations are fetched separately via /analysis/recommendations/<id>.

    CV Preview fields added to response:
        raw_text       — full extracted CV text for the preview modal
        sections_data  — dict of section_name → content for header detection
        found_keywords — keywords from the industry/JD pool that ARE present
    """
    user_id = get_jwt_identity()
    data    = request.get_json()
    if not data:
        return jsonify({"error": "Request body is required."}), 400
    resume_id       = data.get("resume_id")
    major           = data.get("major", "").strip().lower()
    job_description = data.get("job_description", "").strip()
    if not resume_id:
        return jsonify({"error": "resume_id is required."}), 400
    if not major:
        return jsonify({"error": "Industry major is required."}), 400
    resume = Resume.query.filter_by(id=resume_id, user_id=user_id).first()
    if not resume:
        return jsonify({"error": "Resume not found."}), 404
    if not os.path.exists(resume.file_path):
        return jsonify({"error": "Resume file not found on server. Please upload again."}), 404

    # STEP 1 — Extract text
    raw_text, error = extract_text_from_file(resume.file_path)
    if error:
        return jsonify({"error": f"Text extraction failed: {error}"}), 422

    # STEP 2 — NLP sections + keyword placement
    sections, error = detect_sections(raw_text)
    if error:
        return jsonify({"error": f"Section detection failed: {error}"}), 422
    keyword_placement, _ = extract_keywords_per_section(sections)
    keyword_placement    = keyword_placement or {}

    # STEP 3 — ATS Score
    scoring_result, error = calculate_ats_score(
        raw_text          = raw_text,
        sections          = sections,
        keyword_placement = keyword_placement,
        major             = major,
        job_description   = job_description or None,
        file_path         = resume.file_path,
    )
    if error:
        return jsonify({"error": f"ATS scoring failed: {error}"}), 422

    # STEP 4 — Build found_keywords list for CV Preview
    # These are keywords from the industry/JD pool that ARE present in the CV.
    found_keywords = _get_found_keywords(
        raw_text       = raw_text,
        major          = major,
        job_description = job_description or None,
        missing_keywords = scoring_result.get("missing_keywords", []),
    )

    # STEP 5 — Save score to DB
    try:
        resume.raw_text    = raw_text
        resume.parsed_data = sections
        jd_id = None
        if job_description:
            from app.models.analysis import JobDescription
            jd = JobDescription(
                user_id=user_id, title=f"JD for {resume.file_name}",
                description=job_description,
            )
            db.session.add(jd)
            db.session.flush()
            jd_id = jd.id
        analysis = ResumeAnalysis(
            resume_id=resume.id, user_id=user_id,
            job_description_id=jd_id, major=major,
            overall_score=scoring_result["overall_score"],
        )
        db.session.add(analysis)
        db.session.flush()
        ats_result = AtsResult(
            analysis_id=analysis.id, job_description_id=jd_id,
            ats_score                = scoring_result["overall_score"],
            keyword_score            = scoring_result["keyword_score"],
            keyword_placement_score  = scoring_result["keyword_placement_score"],
            formatting_score         = scoring_result["formatting_score"],
            structure_score          = scoring_result["structure_score"],
            experience_recency_score = scoring_result["experience_recency_score"],
            achievements_score       = scoring_result["achievements_score"],
            job_title_score          = scoring_result["job_title_score"],
            education_score          = scoring_result["education_score"],
            resume_length_score      = scoring_result["resume_length_score"],
            contact_info_score       = scoring_result["contact_info_score"],
            missing_sections         = scoring_result["missing_sections"],
            missing_keywords         = scoring_result["missing_keywords"],
        )
        db.session.add(ats_result)
        for section_name, content in sections.items():
            try:
                section_enum = SectionTypeEnum(section_name)
            except ValueError:
                section_enum = SectionTypeEnum.other
            section_row = ResumeSection(
                resume_id=resume.id, section_type=section_enum,
                section_content=content,
            )
            db.session.add(section_row)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"DB save failed for user {user_id}: {e}")
        return jsonify({"error": "Failed to save analysis results. Please try again."}), 500

    return jsonify({
        "message":       "Analysis scored successfully.",
        "analysis_id":   analysis.id,
        "resume_id":     resume.id,
        "overall_score": scoring_result["overall_score"],
        "score_band":    scoring_result["score_band"],
        "used_jd":       scoring_result["used_jd"],
        "scores": {
            "keyword_score":            scoring_result["keyword_score"],
            "keyword_placement_score":  scoring_result["keyword_placement_score"],
            "formatting_score":         scoring_result["formatting_score"],
            "structure_score":          scoring_result["structure_score"],
            "experience_recency_score": scoring_result["experience_recency_score"],
            "achievements_score":       scoring_result["achievements_score"],
            "job_title_score":          scoring_result["job_title_score"],
            "education_score":          scoring_result["education_score"],
            "resume_length_score":      scoring_result["resume_length_score"],
            "contact_info_score":       scoring_result["contact_info_score"],
        },
        "missing_sections":  scoring_result["missing_sections"],
        "missing_keywords":  scoring_result["missing_keywords"],
        "detected_sections": list(sections.keys()),
        # CV Preview fields
        "raw_text":          raw_text,
        "sections_data":     sections,
        "found_keywords":    found_keywords,
        # recommendations are NOT here — phase 2 provides them
        "recommendations":   None,
    }), 200


@analysis_bp.route("/recommendations/<int:analysis_id>", methods=["POST"])
@jwt_required()
def run_recommendations(analysis_id):
    """
    PHASE 2 — GPT recommendations only.

    Loads an existing scored analysis, rebuilds the scoring_result dict
    from the saved AtsResult, calls GPT for recommendations, saves the
    recommendation rows, and returns them.
    """
    user_id  = get_jwt_identity()
    analysis = ResumeAnalysis.query.filter_by(id=analysis_id, user_id=user_id).first()
    if not analysis:
        return jsonify({"error": "Analysis not found."}), 404

    resume = Resume.query.filter_by(id=analysis.resume_id, user_id=user_id).first()
    if not resume:
        return jsonify({"error": "Resume not found."}), 404

    ats = AtsResult.query.filter_by(analysis_id=analysis.id).first()
    if not ats:
        return jsonify({"error": "Score data not found for this analysis."}), 404

    sections = resume.parsed_data or {}
    if not sections:
        return jsonify({"error": "Parsed CV data not found. Please re-run analysis."}), 422

    job_description = None
    if analysis.job_description_id:
        from app.models.analysis import JobDescription
        jd = JobDescription.query.get(analysis.job_description_id)
        job_description = jd.description if jd else None

    scoring_result = {
        "overall_score":            ats.ats_score,
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
        "score_band":               _band_from_score(ats.ats_score),
        "used_jd":                  bool(analysis.job_description_id),
    }

    recommendations, error = generate_recommendations(
        sections=sections, scoring_result=scoring_result,
        major=analysis.major, job_description=job_description or None,
    )
    if error:
        current_app.logger.warning(f"LLM recommendations failed: {error}")
        return jsonify({"error": f"Recommendations failed: {error}"}), 502

    try:
        section_rows   = ResumeSection.query.filter_by(resume_id=resume.id).all()
        section_id_map = {s.section_type.value: s.id for s in section_rows}

        if recommendations and "sections" in recommendations:
            for rec in recommendations["sections"]:
                section_name = rec.get("section", "")
                recommendation_row = Recommendation(
                    analysis_id=analysis.id,
                    section_id=section_id_map.get(section_name),
                    title=rec.get("issue", "")[:255],
                    description=rec.get("recommendation", ""),
                    priority=rec.get("priority", 2),
                )
                db.session.add(recommendation_row)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.warning(f"Saving recommendations failed (non-fatal): {e}")

    return jsonify({
        "analysis_id":     analysis.id,
        "recommendations": recommendations,
    }), 200


# ── Helpers ───────────────────────────────────────────────────────────────────

def _band_from_score(score: float) -> str:
    """Derive score band from overall score."""
    if score is None: return "weak"
    if score >= 75:   return "strong"
    if score >= 65:   return "good"
    if score >= 50:   return "borderline"
    return "weak"


def _get_found_keywords(
    raw_text: str,
    major: str,
    job_description: str,
    missing_keywords: list,
) -> list:
    """
    Return keywords from the industry/JD pool that ARE present in the CV.
    Used by the frontend CV preview to highlight found keywords in blue.

    Strategy:
        Load the same keyword pool the scoring service used (industry DB or JD),
        subtract the missing_keywords list, return what remains that appears
        in the raw text. Capped at 40 to keep the response size reasonable.
    """
    try:
        raw_lower   = raw_text.lower()
        missing_set = {kw.lower() for kw in (missing_keywords or [])}

        if job_description and job_description.strip():
            # JD mode — parse the same pool scoring_service used
            from app.services.scoring_service import _parse_jd_keywords
            jd_required, jd_preferred = _parse_jd_keywords(job_description)
            all_keywords = jd_required + jd_preferred
        else:
            # Industry mode — load from keyword database
            from app.data.keywords.keywords_loader import get_keywords
            required, preferred = get_keywords(major or "technology")
            all_keywords = required + preferred

        found = [
            kw for kw in all_keywords
            if kw.lower() not in missing_set and kw.lower() in raw_lower
        ]
        # Deduplicate preserving order, cap at 40
        seen  = set()
        deduped = []
        for kw in found:
            kl = kw.lower()
            if kl not in seen:
                seen.add(kl)
                deduped.append(kw)
        return deduped[:40]

    except Exception as e:
        # Non-fatal — preview still works with just missing highlights
        return []


@analysis_bp.route("/<int:analysis_id>", methods=["GET"])
@jwt_required()
def get_analysis(analysis_id):
    """Retrieve a completed analysis result by ID."""
    user_id  = get_jwt_identity()
    analysis = ResumeAnalysis.query.filter_by(id=analysis_id, user_id=user_id).first()
    if not analysis:
        return jsonify({"error": "Analysis not found."}), 404
    ats      = AtsResult.query.filter_by(analysis_id=analysis.id).first()
    recs     = Recommendation.query.filter_by(
        analysis_id=analysis.id).order_by(Recommendation.priority).all()
    sections = ResumeSection.query.filter_by(resume_id=analysis.resume_id).all()
    return jsonify({
        "analysis_id":   analysis.id,
        "resume_id":     analysis.resume_id,
        "major":         analysis.major,
        "overall_score": analysis.overall_score,
        "created_at":    analysis.created_at.isoformat(),
        "scores": {
            "keyword_score":            ats.keyword_score            if ats else None,
            "keyword_placement_score":  ats.keyword_placement_score  if ats else None,
            "formatting_score":         ats.formatting_score         if ats else None,
            "structure_score":          ats.structure_score          if ats else None,
            "experience_recency_score": ats.experience_recency_score if ats else None,
            "achievements_score":       ats.achievements_score       if ats else None,
            "job_title_score":          ats.job_title_score          if ats else None,
            "education_score":          ats.education_score          if ats else None,
            "resume_length_score":      ats.resume_length_score      if ats else None,
            "contact_info_score":       ats.contact_info_score       if ats else None,
        } if ats else {},
        "missing_sections": ats.missing_sections if ats else [],
        "missing_keywords": ats.missing_keywords if ats else [],
        "recommendations": [
            {"id": r.id, "section_id": r.section_id,
             "title": r.title, "description": r.description,
             "priority": r.priority}
            for r in recs
        ],
        "sections": [
            {"section_type": s.section_type.value,
             "section_content": s.section_content}
            for s in sections
        ],
    }), 200


@analysis_bp.route("/history", methods=["GET"])
@jwt_required()
def get_history():
    """Get all analyses for the current user, most recent first."""
    user_id  = get_jwt_identity()
    analyses = ResumeAnalysis.query.filter_by(user_id=user_id).order_by(
        ResumeAnalysis.created_at.desc()).all()
    return jsonify({
        "analyses": [
            {"analysis_id": a.id, "resume_id": a.resume_id,
             "major": a.major, "overall_score": a.overall_score,
             "created_at": a.created_at.isoformat()}
            for a in analyses
        ],
        "total": len(analyses),
    }), 200